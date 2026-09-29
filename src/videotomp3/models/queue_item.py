from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ItemStatus(str, Enum):
    WAITING = "Waiting"
    CHECKING = "Checking"
    CONVERTING = "Converting"
    COMPLETED = "Completed"
    FAILED = "Failed"
    NO_AUDIO = "No Audio"
    INVALID_MEDIA = "Invalid Media"
    CANCELLED = "Cancelled"
    SKIPPED = "Skipped"


@dataclass
class QueueItem:
    source: Path
    size_bytes: int
    extension: str
    status: ItemStatus = ItemStatus.WAITING
    progress: int = 0
    output: Path | None = None
    duration_seconds: float = 0.0
    error: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
