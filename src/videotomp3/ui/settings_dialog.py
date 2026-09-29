from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLineEdit, QPushButton, QSpinBox, QVBoxLayout
)

from videotomp3.services.settings_service import SettingsService


class SettingsDialog(QDialog):
    def __init__(self, settings: SettingsService, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Settings")
        self.resize(520, 390)

        root = QVBoxLayout(self)

        conversion = QGroupBox("Conversion")
        form = QFormLayout(conversion)
        self.bitrate = QComboBox()
        self.bitrate.addItems(["128", "192", "256", "320"])
        self.bitrate.setCurrentText(str(settings.bitrate))
        form.addRow("Default bitrate (kbps)", self.bitrate)

        folder_row = QHBoxLayout()
        self.folder = QLineEdit(settings.output_folder)
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse_folder)
        folder_row.addWidget(self.folder)
        folder_row.addWidget(browse)
        form.addRow("Default output folder", folder_row)

        self.overwrite = QComboBox()
        self.overwrite.addItem("Ask every time", "ask")
        self.overwrite.addItem("Rename automatically", "rename")
        self.overwrite.addItem("Replace existing file", "replace")
        self.overwrite.addItem("Skip existing file", "skip")
        idx = self.overwrite.findData(settings.overwrite_behavior)
        self.overwrite.setCurrentIndex(max(0, idx))
        form.addRow("Existing file", self.overwrite)

        self.open_after = QCheckBox("Automatically open output folder after conversion")
        self.open_after.setChecked(settings.open_after)
        form.addRow("", self.open_after)
        root.addWidget(conversion)

        appearance = QGroupBox("Appearance")
        aform = QFormLayout(appearance)
        self.theme = QComboBox()
        self.theme.addItem("Dark", "dark")
        self.theme.addItem("Light", "light")
        self.theme.setCurrentIndex(max(0, self.theme.findData(settings.theme)))
        aform.addRow("Theme", self.theme)
        root.addWidget(appearance)

        advanced = QGroupBox("Advanced")
        adv = QFormLayout(advanced)
        ffrow = QHBoxLayout()
        self.ffmpeg_path = QLineEdit(settings.ffmpeg_path)
        ffbrowse = QPushButton("Browse")
        ffbrowse.clicked.connect(self._browse_ffmpeg)
        ffrow.addWidget(self.ffmpeg_path)
        ffrow.addWidget(ffbrowse)
        adv.addRow("FFmpeg path", ffrow)
        self.logging = QCheckBox("Enable troubleshooting log")
        self.logging.setChecked(settings.logging_enabled)
        adv.addRow("", self.logging)
        root.addWidget(advanced)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        save = QPushButton("Save")
        save.setObjectName("primary")
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self._save)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose output folder", self.folder.text())
        if folder:
            self.folder.setText(folder)

    def _browse_ffmpeg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose FFmpeg", self.ffmpeg_path.text(), "FFmpeg (ffmpeg.exe);;All files (*)")
        if path:
            self.ffmpeg_path.setText(path)

    def _save(self) -> None:
        self.settings.bitrate = int(self.bitrate.currentText())
        self.settings.output_folder = self.folder.text().strip()
        self.settings.overwrite_behavior = str(self.overwrite.currentData())
        self.settings.open_after = self.open_after.isChecked()
        self.settings.theme = str(self.theme.currentData())
        self.settings.ffmpeg_path = self.ffmpeg_path.text().strip()
        self.settings.logging_enabled = self.logging.isChecked()
        self.accept()
