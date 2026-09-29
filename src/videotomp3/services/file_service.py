from __future__ import annotations

import os
from pathlib import Path
import shutil
import sys

SUPPORTED_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".flv", ".m4v", ".mpeg", ".mpg"}


def is_supported(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS


def format_size(size: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def auto_rename(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    idx = 1
    while True:
        candidate = path.with_name(f"{stem} ({idx}){suffix}")
        if not candidate.exists():
            return candidate
        idx += 1


def has_enough_disk_space(output_dir: Path, source_size: int) -> bool:
    try:
        free = shutil.disk_usage(output_dir).free
        # Audio is normally much smaller than video; reserve at least source size + 100 MB.
        required = max(source_size, 100 * 1024 * 1024)
        return free > required
    except OSError:
        return False


def open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        import subprocess
        subprocess.Popen(["open", str(path)])
    else:
        import subprocess
        subprocess.Popen(["xdg-open", str(path)])
