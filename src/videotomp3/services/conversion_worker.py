from __future__ import annotations

import logging
from pathlib import Path
import subprocess
import threading

from PySide6.QtCore import QObject, Signal, Slot

from videotomp3.models.queue_item import QueueItem, ItemStatus
from videotomp3.services.ffmpeg_service import FFmpegService, FFmpegError


class ConversionWorker(QObject):
    item_started = Signal(int)
    item_progress = Signal(int, int)
    item_finished = Signal(int, str)
    item_failed = Signal(int, str)
    item_no_audio = Signal(int, str)
    item_cancelled = Signal(int)
    all_finished = Signal()

    def __init__(self, items: list[QueueItem], bitrate: int, ffmpeg: FFmpegService, logger: logging.Logger) -> None:
        super().__init__()
        self.items = items
        self.bitrate = bitrate
        self.ffmpeg = ffmpeg
        self.logger = logger
        self._cancel_event = threading.Event()
        self._current_process: subprocess.Popen[str] | None = None
        self._current_output: Path | None = None

    @Slot()
    def run(self) -> None:
        for index, item in enumerate(self.items):
            if self._cancel_event.is_set():
                item.status = ItemStatus.CANCELLED
                self.item_cancelled.emit(index)
                continue
            if item.status in {ItemStatus.SKIPPED, ItemStatus.COMPLETED, ItemStatus.NO_AUDIO, ItemStatus.INVALID_MEDIA}:
                continue
            try:
                self._convert_one(index, item)
            except FFmpegError as exc:
                friendly = self._friendly_error(exc)
                if "does not contain an audio" in str(exc).lower():
                    self.logger.warning("No audio track | %s", item.source.name)
                    item.status = ItemStatus.NO_AUDIO
                    item.error = friendly
                    self.item_no_audio.emit(index, friendly)
                else:
                    self.logger.error("Conversion error | %s | %s", item.source.name, exc)
                    item.status = ItemStatus.FAILED
                    item.error = friendly
                    self.item_failed.emit(index, friendly)
            except Exception as exc:  # worker boundary: never crash whole application
                self.logger.exception("Unexpected conversion error for %s", item.source)
                item.status = ItemStatus.FAILED
                item.error = str(exc)
                self.item_failed.emit(index, self._friendly_error(exc))
        self._current_process = None
        self._current_output = None
        self.all_finished.emit()

    def _convert_one(self, index: int, item: QueueItem) -> None:
        if not item.output:
            raise RuntimeError("Output path was not prepared.")
        self.item_started.emit(index)
        item.status = ItemStatus.CONVERTING
        self.logger.info("Conversion started | %s", item.source.name)

        info = self.ffmpeg.probe(item.source)
        item.duration_seconds = info.duration
        item.metadata = info.metadata
        if not info.has_audio:
            raise FFmpegError("This video does not contain an audio track.")
        if info.duration <= 0:
            raise FFmpegError("Unable to determine the media duration.")

        args = self.ffmpeg.build_conversion_args(item.source, item.output, self.bitrate)
        self._current_output = item.output
        startupinfo = None
        creationflags = 0
        if hasattr(subprocess, "STARTUPINFO"):
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        self._current_process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )

        stderr_lines: list[str] = []
        stderr_thread = threading.Thread(
            target=self._drain_stderr,
            args=(self._current_process, stderr_lines),
            daemon=True,
        )
        stderr_thread.start()

        assert self._current_process.stdout is not None
        for raw in self._current_process.stdout:
            if self._cancel_event.is_set():
                self._terminate_current()
                self._cleanup_partial()
                item.status = ItemStatus.CANCELLED
                self.logger.info("Conversion cancelled | %s", item.source.name)
                self.item_cancelled.emit(index)
                return
            line = raw.strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key in {"out_time_ms", "out_time_us"}:
                try:
                    microseconds = int(value)
                    seconds = microseconds / 1_000_000.0
                    pct = max(0, min(99, int((seconds / info.duration) * 100)))
                    if pct != item.progress:
                        item.progress = pct
                        self.item_progress.emit(index, pct)
                except ValueError:
                    pass
            elif key == "progress" and value == "end":
                item.progress = 100
                self.item_progress.emit(index, 100)

        return_code = self._current_process.wait()
        stderr_thread.join(timeout=1)
        if self._cancel_event.is_set():
            self._cleanup_partial()
            item.status = ItemStatus.CANCELLED
            self.item_cancelled.emit(index)
            return
        if return_code != 0 or not item.output.exists() or item.output.stat().st_size == 0:
            self._cleanup_partial()
            detail = "\n".join(stderr_lines[-12:]).strip()
            self.logger.error("Conversion failed | %s | %s", item.source.name, detail)
            raise FFmpegError(detail or "FFmpeg was unable to create the MP3 file.")

        item.status = ItemStatus.COMPLETED
        item.progress = 100
        self.logger.info("Conversion completed | %s", item.source.name)
        self.item_finished.emit(index, str(item.output))

    def _drain_stderr(self, process: subprocess.Popen[str], sink: list[str]) -> None:
        if process.stderr is None:
            return
        for line in process.stderr:
            sink.append(line.rstrip())
            if len(sink) > 100:
                del sink[:50]

    @Slot()
    def cancel(self) -> None:
        self._cancel_event.set()
        self._terminate_current()

    def _terminate_current(self) -> None:
        process = self._current_process
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
            except OSError:
                pass

    def _cleanup_partial(self) -> None:
        try:
            if self._current_output and self._current_output.exists():
                self._current_output.unlink()
        except OSError:
            self.logger.warning("Could not remove incomplete output: %s", self._current_output)

    @staticmethod
    def _friendly_error(exc: Exception) -> str:
        message = str(exc).strip()
        low = message.lower()
        if "does not contain an audio" in low or "stream map" in low:
            return "Unable to convert this video because it does not contain an audio track."
        if "permission" in low or "access is denied" in low:
            return "The output file or folder cannot be written. Check folder permissions and try again."
        if "no space" in low or "disk full" in low:
            return "There is not enough free disk space to complete this conversion."
        if "invalid" in low or "corrupt" in low:
            return "Unable to convert this video. The file may be corrupted or unsupported."
        return "Unable to convert this video. Check the file and output folder, then try again."
