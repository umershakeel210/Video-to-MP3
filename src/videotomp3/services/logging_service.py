from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys


def app_data_dir() -> Path:
    if sys.platform == "win32":
        import os
        base = Path(os.environ.get("LOCALAPPDATA", Path.home()))
        path = base / "VideoToMP3"
    else:
        path = Path.home() / ".video_to_mp3"
    path.mkdir(parents=True, exist_ok=True)
    return path


def configure_logging(enabled: bool = True) -> logging.Logger:
    logger = logging.getLogger("videotomp3")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    if enabled:
        log_file = app_data_dir() / "videotomp3.log"
        handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        logger.addHandler(handler)
    else:
        logger.addHandler(logging.NullHandler())
    logger.info("Application started")
    return logger
