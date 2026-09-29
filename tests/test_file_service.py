from pathlib import Path
from videotomp3.services.file_service import auto_rename, format_size, is_supported


def test_format_size():
    assert format_size(1024) == "1.0 KB"
    assert format_size(1024 * 1024) == "1.0 MB"


def test_supported_file(tmp_path: Path):
    p = tmp_path / "movie.mp4"
    p.write_bytes(b"x")
    assert is_supported(p)


def test_auto_rename(tmp_path: Path):
    p = tmp_path / "song.mp3"
    p.write_bytes(b"x")
    assert auto_rename(p).name == "song (1).mp3"
