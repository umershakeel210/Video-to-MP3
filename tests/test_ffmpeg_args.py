from pathlib import Path
from videotomp3.services.ffmpeg_service import FFmpegService


def test_build_args_keep_paths_as_separate_arguments():
    service = FFmpegService()
    service.ffmpeg = "ffmpeg"
    src = Path("C:/Video Files/hello & world.mp4")
    out = Path("C:/Output Files/hello & world.mp3")
    args = service.build_conversion_args(src, out, 192)
    assert str(src) in args
    assert str(out) in args
    assert "192k" in args
    assert isinstance(args, list)
