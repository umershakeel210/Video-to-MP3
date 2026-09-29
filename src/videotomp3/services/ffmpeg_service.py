from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from dataclasses import dataclass


class FFmpegError(RuntimeError):
    pass


@dataclass(frozen=True)
class MediaInfo:
    duration: float
    has_audio: bool
    metadata: dict[str, str]


class FFmpegService:
    def __init__(self, configured_path: str = "") -> None:
        self.configured_path = configured_path.strip()
        self.ffmpeg = self._resolve_binary("ffmpeg")
        self.ffprobe = self._resolve_binary("ffprobe")

    def _candidate_bases(self) -> list[Path]:
        bases: list[Path] = []
        if getattr(sys, "frozen", False):
            bases.append(Path(sys.executable).resolve().parent)
        bases.extend([
            Path(__file__).resolve().parents[3],
            Path.cwd(),
        ])
        return bases

    def _resolve_binary(self, name: str) -> str | None:
        suffix = ".exe" if os.name == "nt" else ""
        if name == "ffmpeg" and self.configured_path:
            p = Path(self.configured_path).expanduser()
            if p.is_file():
                return str(p)
            if p.is_dir():
                candidate = p / f"{name}{suffix}"
                if candidate.is_file():
                    return str(candidate)
        if name == "ffprobe" and self.configured_path:
            p = Path(self.configured_path).expanduser()
            directory = p.parent if p.is_file() else p
            candidate = directory / f"{name}{suffix}"
            if candidate.is_file():
                return str(candidate)
        for base in self._candidate_bases():
            candidate = base / "ffmpeg" / "bin" / f"{name}{suffix}"
            if candidate.is_file():
                return str(candidate)
            candidate2 = base / "ffmpeg" / f"{name}{suffix}"
            if candidate2.is_file():
                return str(candidate2)
        return shutil.which(name)

    @property
    def available(self) -> bool:
        return bool(self.ffmpeg and self.ffprobe)

    def verify(self) -> tuple[bool, str]:
        if not self.ffmpeg:
            return False, "FFmpeg was not found. Bundle it with the application or configure its path in Settings."
        if not self.ffprobe:
            return False, "FFprobe was not found next to FFmpeg or in the system PATH."
        try:
            subprocess.run([self.ffmpeg, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=5)
            subprocess.run([self.ffprobe, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=5)
            return True, "FFmpeg detected"
        except (subprocess.SubprocessError, OSError) as exc:
            return False, f"FFmpeg could not be started: {exc}"

    def probe(self, source: Path) -> MediaInfo:
        if not self.ffprobe:
            raise FFmpegError("FFprobe is unavailable.")
        args = [
            self.ffprobe,
            "-v", "error",
            "-show_entries", "format=duration:format_tags=title,artist,album:stream=codec_type",
            "-of", "json",
            str(source),
        ]
        try:
            result = subprocess.run(args, capture_output=True, text=True, check=False, timeout=30)
        except OSError as exc:
            raise FFmpegError(f"Unable to inspect media: {exc}") from exc
        if result.returncode != 0:
            raise FFmpegError("The selected file is corrupted, invalid, or unsupported.")
        try:
            data = json.loads(result.stdout or "{}")
            duration = float(data.get("format", {}).get("duration") or 0.0)
            streams = data.get("streams", [])
            has_audio = any(s.get("codec_type") == "audio" for s in streams)
            tags = data.get("format", {}).get("tags") or {}
            metadata = {k.lower(): str(v) for k, v in tags.items() if k.lower() in {"title", "artist", "album"}}
            return MediaInfo(duration=duration, has_audio=has_audio, metadata=metadata)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise FFmpegError("Unable to read media information.") from exc

    def build_conversion_args(self, source: Path, output: Path, bitrate: int) -> list[str]:
        if not self.ffmpeg:
            raise FFmpegError("FFmpeg is unavailable.")
        return [
            self.ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-y",
            "-i", str(source),
            "-map", "0:a:0",
            "-vn",
            "-c:a", "libmp3lame",
            "-b:a", f"{bitrate}k",
            "-map_metadata", "0",
            "-progress", "pipe:1",
            "-nostats",
            str(output),
        ]
