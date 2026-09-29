from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
)

from videotomp3.models.queue_item import QueueItem, ItemStatus
from videotomp3.services.conversion_worker import ConversionWorker
from videotomp3.services.ffmpeg_service import FFmpegService, FFmpegError
from videotomp3.services.file_service import SUPPORTED_EXTENSIONS, auto_rename, format_size, has_enough_disk_space, is_supported
from videotomp3.services.logging_service import app_data_dir
from videotomp3.services.settings_service import SettingsService
from videotomp3.ui.settings_dialog import SettingsDialog
from videotomp3.ui.themes import DARK, LIGHT


class DropZone(QFrame):
    files_dropped = Signal(list)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("dropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(120)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        title = QLabel("🎬  DROP VIDEO FILES HERE")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 16pt; font-weight: 700; background: transparent;")
        sub = QLabel("or click Browse Videos")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet("background: transparent;")
        layout.addWidget(title)
        layout.addWidget(sub)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        self.files_dropped.emit(paths)
        event.acceptProposedAction()


class MainWindow(QMainWindow):
    def __init__(self, settings: SettingsService, logger: logging.Logger) -> None:
        super().__init__()
        self.settings = settings
        self.logger = logger
        self.items: list[QueueItem] = []
        self.thread: QThread | None = None
        self.worker: ConversionWorker | None = None
        self.last_output_dir: Path | None = None
        self.setWindowTitle("Video to MP3 Converter")
        self.resize(1050, 720)
        self.setMinimumSize(850, 600)
        self._build_ui()
        self.apply_theme()
        self._refresh_buttons()
        self._check_ffmpeg(show_success=False)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        top = QHBoxLayout()
        titlebox = QVBoxLayout()
        title = QLabel("Video → MP3 Converter")
        title.setStyleSheet("font-size: 22pt; font-weight: 750;")
        subtitle = QLabel("Fast batch audio extraction with real FFmpeg progress")
        titlebox.addWidget(title)
        titlebox.addWidget(subtitle)
        top.addLayout(titlebox)
        top.addStretch(1)
        self.theme_btn = QPushButton("Light mode" if self.settings.theme == "dark" else "Dark mode")
        self.settings_btn = QPushButton("Settings")
        self.theme_btn.clicked.connect(self._toggle_theme)
        self.settings_btn.clicked.connect(self._open_settings)
        top.addWidget(self.theme_btn)
        top.addWidget(self.settings_btn)
        root.addLayout(top)

        self.drop = DropZone()
        self.drop.files_dropped.connect(self._add_paths)
        root.addWidget(self.drop)

        toolbar = QHBoxLayout()
        self.browse_btn = QPushButton("Browse Videos")
        self.remove_btn = QPushButton("Remove Selected")
        self.clear_btn = QPushButton("Clear Queue")
        self.browse_btn.clicked.connect(self._browse)
        self.remove_btn.clicked.connect(self._remove_selected)
        self.clear_btn.clicked.connect(self._clear_queue)
        toolbar.addWidget(self.browse_btn)
        toolbar.addWidget(self.remove_btn)
        toolbar.addWidget(self.clear_btn)
        toolbar.addStretch(1)
        toolbar.addWidget(QLabel("Quality"))
        self.quality = QComboBox()
        self.quality.addItems(["128 kbps", "192 kbps", "256 kbps", "320 kbps"])
        self.quality.setCurrentText(f"{self.settings.bitrate} kbps")
        toolbar.addWidget(self.quality)
        toolbar.addWidget(QLabel("Output"))
        self.output_mode = QComboBox()
        self.output_mode.addItem("Same folder as source", "same")
        self.output_mode.addItem("Custom folder", "custom")
        self.output_mode.setCurrentIndex(max(0, self.output_mode.findData(self.settings.output_mode)))
        self.output_mode.currentIndexChanged.connect(self._save_output_mode)
        toolbar.addWidget(self.output_mode)
        self.choose_output_btn = QPushButton("Choose Folder")
        self.choose_output_btn.clicked.connect(self._choose_output)
        toolbar.addWidget(self.choose_output_btn)
        root.addLayout(toolbar)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["File", "Size", "Format", "Status", "Progress"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2, 3, 4):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        root.addWidget(self.table, 1)

        progress_row = QHBoxLayout()
        status_col = QVBoxLayout()
        self.current_label = QLabel("Ready")
        self.count_label = QLabel("0 files in queue")
        status_col.addWidget(self.current_label)
        status_col.addWidget(self.count_label)
        progress_row.addLayout(status_col, 1)
        self.overall_progress = QProgressBar()
        self.overall_progress.setRange(0, 100)
        self.overall_progress.setValue(0)
        self.overall_progress.setFormat("Batch processed: 0%")
        self.overall_progress.setMinimumWidth(320)
        progress_row.addWidget(self.overall_progress)
        root.addLayout(progress_row)

        actions = QHBoxLayout()
        self.ffmpeg_status = QLabel("Checking FFmpeg…")
        actions.addWidget(self.ffmpeg_status)
        actions.addStretch(1)
        self.logs_btn = QPushButton("Open Logs")
        self.open_output_btn = QPushButton("Open Output Folder")
        self.cancel_btn = QPushButton("Cancel")
        self.start_btn = QPushButton("Convert to MP3")
        self.start_btn.setObjectName("primary")
        self.logs_btn.clicked.connect(self._open_logs)
        self.open_output_btn.clicked.connect(self._open_output)
        self.cancel_btn.clicked.connect(self._cancel)
        self.start_btn.clicked.connect(self._start)
        actions.addWidget(self.logs_btn)
        actions.addWidget(self.open_output_btn)
        actions.addWidget(self.cancel_btn)
        actions.addWidget(self.start_btn)
        root.addLayout(actions)

    def apply_theme(self) -> None:
        QApplication.instance().setStyleSheet(DARK if self.settings.theme == "dark" else LIGHT)
        self.theme_btn.setText("Light mode" if self.settings.theme == "dark" else "Dark mode")

    def _toggle_theme(self) -> None:
        self.settings.theme = "light" if self.settings.theme == "dark" else "dark"
        self.apply_theme()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.quality.setCurrentText(f"{self.settings.bitrate} kbps")
            self.apply_theme()
            self._check_ffmpeg(show_success=True)

    def _browse(self) -> None:
        patterns = " ".join(f"*{e}" for e in sorted(SUPPORTED_EXTENSIONS))
        files, _ = QFileDialog.getOpenFileNames(self, "Select video files", "", f"Video files ({patterns});;All files (*)")
        self._add_paths(files)

    def _add_paths(self, paths: list[str]) -> None:
        existing = {i.source.resolve() for i in self.items}
        unsupported: list[str] = []
        added = 0
        for raw in paths:
            path = Path(raw)
            try:
                resolved = path.resolve()
            except OSError:
                resolved = path
            if not is_supported(path):
                unsupported.append(path.name)
                continue
            if resolved in existing:
                continue
            try:
                size = path.stat().st_size
            except OSError:
                unsupported.append(path.name)
                continue
            item = QueueItem(source=path, size_bytes=size, extension=path.suffix[1:].upper())
            self.items.append(item)
            existing.add(resolved)
            self._append_row(item)
            self.logger.info("File added | %s", path.name)
            added += 1
        if unsupported:
            shown = "\n".join(unsupported[:8])
            extra = "" if len(unsupported) <= 8 else f"\n…and {len(unsupported)-8} more"
            QMessageBox.warning(self, "Unsupported file", f"These files were not added because they are unsupported or unavailable:\n\n{shown}{extra}")
        if added:
            self._update_summary()
        self._refresh_buttons()

    def _append_row(self, item: QueueItem) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(item.source.name))
        self.table.setItem(row, 1, QTableWidgetItem(format_size(item.size_bytes)))
        self.table.setItem(row, 2, QTableWidgetItem(item.extension))
        self.table.setItem(row, 3, QTableWidgetItem(item.status.value))
        self.table.setItem(row, 4, QTableWidgetItem("—"))
        self.table.item(row, 0).setToolTip(str(item.source))

    def _remove_selected(self) -> None:
        rows = sorted({idx.row() for idx in self.table.selectionModel().selectedRows()}, reverse=True)
        for row in rows:
            self.table.removeRow(row)
            del self.items[row]
        self._update_summary()
        self._refresh_buttons()

    def _clear_queue(self) -> None:
        self.items.clear()
        self.table.setRowCount(0)
        self.overall_progress.setValue(0)
        self.overall_progress.setFormat("Batch processed: 0%")
        self.current_label.setText("Ready")
        self._update_summary()
        self._refresh_buttons()

    def _save_output_mode(self) -> None:
        self.settings.output_mode = str(self.output_mode.currentData())
        self._refresh_buttons()

    def _choose_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder", self.settings.output_folder)
        if folder:
            self.settings.output_folder = folder
            self.output_mode.setCurrentIndex(self.output_mode.findData("custom"))

    def _preflight_media(self) -> bool:
        """Inspect queued files before conversion so no-audio/invalid files are not treated as conversion failures."""
        ffmpeg = FFmpegService(self.settings.ffmpeg_path)
        candidates = [
            (row, item)
            for row, item in enumerate(self.items)
            if item.status not in {ItemStatus.COMPLETED, ItemStatus.SKIPPED}
        ]
        if not candidates:
            return False

        for row, item in candidates:
            item.status = ItemStatus.CHECKING
            item.error = ""
            item.progress = 0
            self._set_row(row, status=ItemStatus.CHECKING.value, progress="—")
            self.current_label.setText(f"Checking audio: {item.source.name}")
            QApplication.processEvents()
            try:
                info = ffmpeg.probe(item.source)
                item.duration_seconds = info.duration
                item.metadata = info.metadata
                if not info.has_audio:
                    item.status = ItemStatus.NO_AUDIO
                    item.error = (
                        "No audio track was found in this file. "
                        "The file contains video only, so there is no audio available to convert to MP3."
                    )
                    self._set_row(row, status=ItemStatus.NO_AUDIO.value, progress="—")
                    self.table.item(row, 3).setToolTip(item.error)
                    self.logger.warning("No audio track detected during preflight | %s", item.source.name)
                    continue
                if info.duration <= 0:
                    raise FFmpegError("Unable to determine the media duration.")
                item.status = ItemStatus.WAITING
                self._set_row(row, status=ItemStatus.WAITING.value, progress="—")
            except FFmpegError as exc:
                item.status = ItemStatus.INVALID_MEDIA
                item.error = str(exc) or "The media file could not be inspected."
                self._set_row(row, status=ItemStatus.INVALID_MEDIA.value, progress="—")
                self.table.item(row, 3).setToolTip(item.error)
                self.logger.warning("Invalid media during preflight | %s | %s", item.source.name, exc)

        self.current_label.setText("Ready")
        self._update_summary()
        return any(item.status == ItemStatus.WAITING for item in self.items)

    def _prepare_outputs(self) -> bool:
        custom_dir = Path(self.settings.output_folder).expanduser() if self.output_mode.currentData() == "custom" else None
        if custom_dir:
            try:
                custom_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                QMessageBox.critical(self, "Invalid output folder", "The selected output folder cannot be created or written.")
                return False
            if not custom_dir.is_dir():
                QMessageBox.critical(self, "Invalid output folder", "Please choose a valid output folder.")
                return False

        behavior = self.settings.overwrite_behavior
        for row, item in enumerate(self.items):
            if item.status in {ItemStatus.COMPLETED, ItemStatus.NO_AUDIO, ItemStatus.INVALID_MEDIA, ItemStatus.SKIPPED}:
                continue
            out_dir = custom_dir or item.source.parent
            output = out_dir / f"{item.source.stem}.mp3"
            if not has_enough_disk_space(out_dir, item.size_bytes):
                QMessageBox.critical(self, "Not enough disk space", f"There may not be enough free disk space in:\n{out_dir}")
                return False
            if output.exists():
                choice = behavior
                if behavior == "ask":
                    box = QMessageBox(self)
                    box.setWindowTitle("File already exists")
                    box.setText(f"{output.name} already exists.")
                    replace = box.addButton("Replace", QMessageBox.AcceptRole)
                    rename = box.addButton("Rename automatically", QMessageBox.ActionRole)
                    skip = box.addButton("Skip", QMessageBox.RejectRole)
                    box.exec()
                    clicked = box.clickedButton()
                    if clicked is replace:
                        choice = "replace"
                    elif clicked is rename:
                        choice = "rename"
                    else:
                        choice = "skip"
                if choice == "rename":
                    output = auto_rename(output)
                elif choice == "skip":
                    item.status = ItemStatus.SKIPPED
                    item.progress = 0
                    self._set_row(row, status=ItemStatus.SKIPPED.value, progress="—")
                    continue
            item.output = output
            item.status = ItemStatus.WAITING
            item.progress = 0
            self._set_row(row, status=ItemStatus.WAITING.value, progress="—")
        return any(i.status == ItemStatus.WAITING for i in self.items)

    def _start(self) -> None:
        if self.thread is not None:
            return
        ok, message = self._check_ffmpeg(show_success=False)
        if not ok:
            QMessageBox.critical(self, "FFmpeg required", message)
            return
        if not self.items:
            return
        self.settings.bitrate = int(self.quality.currentText().split()[0])
        if not self._preflight_media():
            no_audio = [i for i in self.items if i.status == ItemStatus.NO_AUDIO]
            invalid = [i for i in self.items if i.status == ItemStatus.INVALID_MEDIA]
            if no_audio or invalid:
                details = []
                if no_audio:
                    details.append(f"No audio track: {len(no_audio)}")
                if invalid:
                    details.append(f"Invalid/unsupported media: {len(invalid)}")
                QMessageBox.warning(
                    self,
                    "Nothing to convert",
                    "No convertible audio was found in the queued file(s).\n\n"
                    + "\n".join(details)
                    + "\n\nFiles marked 'No Audio' contain video only and cannot produce an MP3.",
                )
            return
        if not self._prepare_outputs():
            if all(i.status in {ItemStatus.SKIPPED, ItemStatus.NO_AUDIO, ItemStatus.INVALID_MEDIA, ItemStatus.COMPLETED} for i in self.items):
                QMessageBox.information(self, "Nothing to convert", "There are no remaining files ready for conversion.")
            return

        ffmpeg = FFmpegService(self.settings.ffmpeg_path)
        self.thread = QThread(self)
        self.worker = ConversionWorker(self.items, self.settings.bitrate, ffmpeg, self.logger)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.item_started.connect(self._on_item_started)
        self.worker.item_progress.connect(self._on_item_progress)
        self.worker.item_finished.connect(self._on_item_finished)
        self.worker.item_failed.connect(self._on_item_failed)
        self.worker.item_no_audio.connect(self._on_item_no_audio)
        self.worker.item_cancelled.connect(self._on_item_cancelled)
        self.worker.all_finished.connect(self._on_all_finished)
        self.worker.all_finished.connect(self.thread.quit)
        self.thread.finished.connect(self._cleanup_thread)
        self.thread.start()
        self._refresh_buttons()

    def _cancel(self) -> None:
        if self.worker:
            self.worker.cancel()
            self.current_label.setText("Cancelling…")

    def _on_item_started(self, index: int) -> None:
        self.items[index].status = ItemStatus.CONVERTING
        self.current_label.setText(f"Converting: {self.items[index].source.name}")
        self._set_row(index, status="Converting", progress="0%")
        self._update_summary()

    def _on_item_progress(self, index: int, progress: int) -> None:
        self.items[index].progress = progress
        self._set_row(index, progress=f"{progress}%")
        self._update_summary()

    def _on_item_finished(self, index: int, output: str) -> None:
        item = self.items[index]
        item.status = ItemStatus.COMPLETED
        item.output = Path(output)
        self.last_output_dir = item.output.parent
        self._set_row(index, status="Completed", progress="100%")
        self._update_summary()

    def _on_item_failed(self, index: int, message: str) -> None:
        item = self.items[index]
        item.status = ItemStatus.FAILED
        item.error = message
        self._set_row(index, status="Failed", progress=f"{item.progress}%")
        self.table.item(index, 3).setToolTip(message)
        self._update_summary()

    def _on_item_no_audio(self, index: int, message: str) -> None:
        item = self.items[index]
        item.status = ItemStatus.NO_AUDIO
        item.error = message
        item.progress = 0
        self._set_row(index, status=ItemStatus.NO_AUDIO.value, progress="—")
        self.table.item(index, 3).setToolTip(message)
        self._update_summary()

    def _on_item_cancelled(self, index: int) -> None:
        self.items[index].status = ItemStatus.CANCELLED
        self._set_row(index, status="Cancelled", progress=f"{self.items[index].progress}%")
        self._update_summary()

    def _on_all_finished(self) -> None:
        completed = sum(i.status == ItemStatus.COMPLETED for i in self.items)
        failed = sum(i.status == ItemStatus.FAILED for i in self.items)
        no_audio = sum(i.status == ItemStatus.NO_AUDIO for i in self.items)
        invalid = sum(i.status == ItemStatus.INVALID_MEDIA for i in self.items)
        cancelled = sum(i.status == ItemStatus.CANCELLED for i in self.items)

        if failed or no_audio or invalid:
            self.current_label.setText("Finished with issues")
            lines = [f"Completed: {completed}"]
            if no_audio:
                lines.append(f"No audio track: {no_audio}")
            if invalid:
                lines.append(f"Invalid media: {invalid}")
            if failed:
                lines.append(f"Failed: {failed}")
            if cancelled:
                lines.append(f"Cancelled: {cancelled}")
            lines.append("")
            lines.append("'No Audio' means the source file contains video only; there is no audio data available to convert to MP3.")
            QMessageBox.warning(self, "Conversion finished", "\n".join(lines))
        elif cancelled:
            self.current_label.setText("Conversion cancelled")
            QMessageBox.information(self, "Conversion cancelled", f"Completed: {completed}\nCancelled: {cancelled}")
        else:
            self.current_label.setText("Conversion complete")
            QMessageBox.information(self, "Conversion complete", f"Successfully converted {completed} file(s) to MP3.")
        if self.settings.open_after and self.last_output_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_output_dir)))

    def _cleanup_thread(self) -> None:
        if self.worker:
            self.worker.deleteLater()
        if self.thread:
            self.thread.deleteLater()
        self.worker = None
        self.thread = None
        self._refresh_buttons()

    def _set_row(self, row: int, *, status: str | None = None, progress: str | None = None) -> None:
        if status is not None:
            self.table.item(row, 3).setText(status)
        if progress is not None:
            self.table.item(row, 4).setText(progress)

    def _update_summary(self) -> None:
        total = len(self.items)
        completed = sum(i.status == ItemStatus.COMPLETED for i in self.items)
        failed = sum(i.status == ItemStatus.FAILED for i in self.items)
        no_audio = sum(i.status == ItemStatus.NO_AUDIO for i in self.items)
        invalid = sum(i.status == ItemStatus.INVALID_MEDIA for i in self.items)
        cancelled = sum(i.status == ItemStatus.CANCELLED for i in self.items)
        skipped = sum(i.status == ItemStatus.SKIPPED for i in self.items)
        terminal = {
            ItemStatus.COMPLETED, ItemStatus.FAILED, ItemStatus.NO_AUDIO, ItemStatus.INVALID_MEDIA,
            ItemStatus.CANCELLED, ItemStatus.SKIPPED,
        }
        done_weight = 0.0
        for item in self.items:
            if item.status in terminal:
                done_weight += 100
            else:
                done_weight += item.progress
        overall = int(done_weight / total) if total else 0
        self.overall_progress.setValue(overall)
        self.overall_progress.setFormat(f"Batch processed: {overall}%")
        remaining = max(0, total - completed - failed - no_audio - invalid - cancelled - skipped)
        parts = [f"{completed} completed"]
        if no_audio:
            parts.append(f"{no_audio} no audio")
        if invalid:
            parts.append(f"{invalid} invalid")
        if failed:
            parts.append(f"{failed} failed")
        parts.extend([f"{remaining} remaining", f"{total} total"])
        self.count_label.setText("  •  ".join(parts))

    def _refresh_buttons(self) -> None:
        running = self.thread is not None
        has_items = bool(self.items)
        self.start_btn.setEnabled(has_items and not running)
        self.cancel_btn.setEnabled(running)
        self.remove_btn.setEnabled(has_items and not running)
        self.clear_btn.setEnabled(has_items and not running)
        self.browse_btn.setEnabled(not running)
        self.settings_btn.setEnabled(not running)
        self.quality.setEnabled(not running)
        self.output_mode.setEnabled(not running)
        self.choose_output_btn.setEnabled(not running and self.output_mode.currentData() == "custom")
        self.open_output_btn.setEnabled(self.last_output_dir is not None or bool(self.settings.output_folder))

    def _check_ffmpeg(self, show_success: bool) -> tuple[bool, str]:
        service = FFmpegService(self.settings.ffmpeg_path)
        ok, message = service.verify()
        self.ffmpeg_status.setText("✓ FFmpeg ready" if ok else "⚠ FFmpeg not found")
        self.ffmpeg_status.setToolTip(message)
        if ok:
            self.logger.info("FFmpeg detected")
            if show_success:
                QMessageBox.information(self, "FFmpeg", "FFmpeg and FFprobe were detected successfully.")
        return ok, message

    def _open_output(self) -> None:
        path = self.last_output_dir
        if not path:
            path = Path(self.settings.output_folder) if self.output_mode.currentData() == "custom" else (self.items[0].source.parent if self.items else Path.home())
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_logs(self) -> None:
        log_dir = app_data_dir()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_dir)))

    def closeEvent(self, event) -> None:
        if self.thread is not None:
            answer = QMessageBox.question(self, "Conversion running", "A conversion is still running. Cancel it and exit?", QMessageBox.Yes | QMessageBox.No)
            if answer != QMessageBox.Yes:
                event.ignore()
                return
            if self.worker:
                self.worker.cancel()
            if self.thread:
                self.thread.quit()
                self.thread.wait(4000)
        event.accept()
