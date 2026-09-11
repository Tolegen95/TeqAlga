from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a"}
TEXT_EXTENSIONS = {".txt"}
SUPPORTED_EXTENSIONS = AUDIO_EXTENSIONS | TEXT_EXTENSIONS


class AudioPreparationError(RuntimeError):
    pass


def ensure_supported(path: Path) -> None:
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise AudioPreparationError(f"Unsupported file type. Expected one of: {supported}")


def normalize_audio(source: Path, destination: Path) -> Path:
    """Convert audio to mono, 16 kHz, signed 16-bit PCM WAV."""
    ensure_supported(source)
    if source.suffix.lower() not in AUDIO_EXTENSIONS:
        raise AudioPreparationError("Text transcripts do not need audio normalization")
    if shutil.which("ffmpeg") is None:
        raise AudioPreparationError("FFmpeg is not installed or not available in PATH")

    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(destination),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or "unknown FFmpeg error"
        raise AudioPreparationError(f"Could not prepare audio: {detail}") from exc
    return destination

