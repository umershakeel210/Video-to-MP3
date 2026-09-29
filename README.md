# Video to MP3 Converter

A professional Windows desktop utility for converting one or many video files into MP3 audio using FFmpeg.

## Features

- Browse or drag/drop multiple videos
- MP4, MKV, AVI, MOV, WMV, WebM, FLV, M4V, MPEG and MPG validation
- MP3 quality: 128 / 192 / 256 / 320 kbps
- Same-folder or custom output location
- Existing-file handling: ask, replace, auto-rename, or skip
- Real FFmpeg conversion progress using `-progress pipe:1`
- Per-file state: Waiting, Converting, Completed, Failed, Cancelled, Skipped
- Overall queue progress and completion counters
- Safe cancellation and cleanup of partial output
- Audio-stream validation with FFprobe
- Source metadata mapping where available
- Dark/light themes remembered between sessions
- Persistent settings using QSettings
- Rotating troubleshooting log
- Background worker thread so the UI remains responsive
- FFmpeg executable discovery from bundled files, user settings, or PATH
- PyInstaller build and Inno Setup installer configuration

## Architecture

```text
src/videotomp3/
  main.py
  models/
    queue_item.py
  services/
    conversion_worker.py
    ffmpeg_service.py
    file_service.py
    logging_service.py
    settings_service.py
  ui/
    main_window.py
    settings_dialog.py
    themes.py
```

The UI, conversion process, FFmpeg integration, file/output behavior, settings and logging are separated to keep the application maintainable.

## Development setup

Requirements:

- Windows 10/11 recommended
- Python 3.10+ (3.12 recommended)
- FFmpeg + FFprobe

```powershell
cd VideoToMP3
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt pytest
$env:PYTHONPATH = "$PWD\src"
python -m videotomp3.main
```

## FFmpeg setup

The application checks in this order:

1. User-configured FFmpeg path in Settings
2. `ffmpeg/bin/ffmpeg.exe` and `ffmpeg/bin/ffprobe.exe` beside the packaged app/project
3. `ffmpeg/ffmpeg.exe` and `ffmpeg/ffprobe.exe`
4. System PATH

To make a self-contained Windows build, put `ffmpeg.exe` and `ffprobe.exe` into `ffmpeg/bin/` before building. Confirm your selected FFmpeg build and redistribution method comply with its license.

## Run tests

```powershell
$env:PYTHONPATH = "$PWD\src"
pytest -q
```

## Build Windows EXE

The provided script creates the venv if needed, installs packaging tools, runs tests and builds the EXE:

```powershell
.\build.ps1
```

Result:

```text
dist\VideoToMP3.exe
```

## Build installer

Install Inno Setup, then compile `installer.iss` after the PyInstaller build.

Result:

```text
installer_output\VideoToMP3-Setup.exe
```

## User workflow

1. Open the application.
2. Drop or browse one or more videos.
3. Select MP3 quality.
4. Choose same-source folder or a custom output folder.
5. Click **Convert to MP3**.
6. Monitor real per-file and overall progress.
7. Review Completed/Failed states.
8. Open the output folder.

## Error handling

User-facing errors are simplified. Detailed diagnostic information is written to:

```text
%LOCALAPPDATA%\VideoToMP3\videotomp3.log
```

The UI does not display Python stack traces.

## Testing checklist

### Basic
- [ ] MP4 → MP3
- [ ] MKV → MP3
- [ ] Multiple files
- [ ] Drag and drop
- [ ] Browse selection

### Edge cases
- [ ] Corrupted video
- [ ] Video without audio
- [ ] Very large video
- [ ] Very short video
- [ ] Existing output file: replace
- [ ] Existing output file: rename
- [ ] Existing output file: skip
- [ ] Unsupported extension
- [ ] Missing FFmpeg
- [ ] Insufficient disk space
- [ ] Invalid/unwritable output directory
- [ ] Cancel conversion mid-file and verify partial MP3 cleanup

### UI
- [ ] Dark mode
- [ ] Light mode
- [ ] Window resize
- [ ] Long filenames
- [ ] Large queue
- [ ] Error messages
- [ ] Real progress updates

## Notes

The application performs conversions sequentially by design. This reduces CPU/disk contention on normal desktop PCs and keeps progress and cancellation predictable. The architecture can be extended later for bounded parallel conversion if there is a demonstrated need.

## Version 1.1.0 - media preflight fix

- Checks each queued media file for an audio stream before conversion.
- Files that contain video only are marked **No Audio** instead of generic **Failed**.
- Invalid/corrupted media is marked **Invalid Media** before FFmpeg conversion starts.
- No-audio files are not repeatedly retried in the same queue.
- Batch progress is labeled **Batch processed** so 100% cannot be mistaken for 100% successful conversions.
- Completion dialog now separates Completed, No Audio, Invalid Media, Failed, and Cancelled counts.
- The conversion worker keeps a second audio-stream check as a safety fallback.

A video-only MP4/DASH file cannot be converted to MP3 because there is no audio data in that file. The application now explains this clearly instead of presenting it as an ordinary conversion failure.
