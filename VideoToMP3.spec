# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH)
ffmpeg_files = []
for name in ("ffmpeg.exe", "ffprobe.exe"):
    p1 = root / "ffmpeg" / "bin" / name
    p2 = root / "ffmpeg" / name
    if p1.exists():
        ffmpeg_files.append((str(p1), "ffmpeg/bin"))
    elif p2.exists():
        ffmpeg_files.append((str(p2), "ffmpeg"))

a = Analysis(
    [str(root / "src" / "videotomp3" / "main.py")],
    pathex=[str(root / "src")],
    binaries=ffmpeg_files,
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="VideoToMP3",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)
