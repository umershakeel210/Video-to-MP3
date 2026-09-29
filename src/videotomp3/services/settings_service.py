from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QSettings, QStandardPaths


class SettingsService:
    ORG = "UtilityWorks"
    APP = "VideoToMP3"

    def __init__(self) -> None:
        self._settings = QSettings(self.ORG, self.APP)

    def get(self, key: str, default=None):
        return self._settings.value(key, default)

    def set(self, key: str, value) -> None:
        self._settings.setValue(key, value)
        self._settings.sync()

    @property
    def bitrate(self) -> int:
        return int(self.get("conversion/bitrate", 192))

    @bitrate.setter
    def bitrate(self, value: int) -> None:
        self.set("conversion/bitrate", int(value))

    @property
    def output_mode(self) -> str:
        return str(self.get("conversion/output_mode", "same"))

    @output_mode.setter
    def output_mode(self, value: str) -> None:
        self.set("conversion/output_mode", value)

    @property
    def output_folder(self) -> str:
        default = QStandardPaths.writableLocation(QStandardPaths.MusicLocation)
        return str(self.get("conversion/output_folder", default))

    @output_folder.setter
    def output_folder(self, value: str) -> None:
        self.set("conversion/output_folder", value)

    @property
    def overwrite_behavior(self) -> str:
        return str(self.get("conversion/overwrite", "ask"))

    @overwrite_behavior.setter
    def overwrite_behavior(self, value: str) -> None:
        self.set("conversion/overwrite", value)

    @property
    def open_after(self) -> bool:
        raw = self.get("conversion/open_after", False)
        return str(raw).lower() in {"1", "true", "yes"}

    @open_after.setter
    def open_after(self, value: bool) -> None:
        self.set("conversion/open_after", bool(value))

    @property
    def theme(self) -> str:
        return str(self.get("appearance/theme", "dark"))

    @theme.setter
    def theme(self, value: str) -> None:
        self.set("appearance/theme", value)

    @property
    def ffmpeg_path(self) -> str:
        return str(self.get("advanced/ffmpeg_path", ""))

    @ffmpeg_path.setter
    def ffmpeg_path(self, value: str) -> None:
        self.set("advanced/ffmpeg_path", value)

    @property
    def logging_enabled(self) -> bool:
        raw = self.get("advanced/logging", True)
        return str(raw).lower() in {"1", "true", "yes"}

    @logging_enabled.setter
    def logging_enabled(self, value: bool) -> None:
        self.set("advanced/logging", bool(value))
