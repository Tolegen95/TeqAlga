from __future__ import annotations

import gc
from pathlib import Path

from app.config import Settings
from app.models import TranscriptSegment


class TranscriptionError(RuntimeError):
    pass


def _runtime_options(settings: Settings) -> tuple[str, str]:
    device = settings.whisper_device
    if device == "auto":
        try:
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"

    compute_type = settings.whisper_compute_type
    if compute_type == "auto":
        compute_type = "float16" if device == "cuda" else "int8"
    return device, compute_type


def transcribe(audio_path: Path, settings: Settings) -> tuple[list[TranscriptSegment], str, float]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise TranscriptionError(
            "faster-whisper is missing. Install requirements/ai.txt first."
        ) from exc

    device, compute_type = _runtime_options(settings)
    settings.whisper_download_root.mkdir(parents=True, exist_ok=True)

    try:
        model = WhisperModel(
            settings.whisper_model,
            device=device,
            compute_type=compute_type,
            download_root=str(settings.whisper_download_root),
        )
        raw_segments, info = model.transcribe(
            str(audio_path),
            beam_size=5,
            vad_filter=True,
            word_timestamps=True,
            condition_on_previous_text=True,
        )
        segments = [
            TranscriptSegment(
                id=f"seg_{index:04d}",
                start=float(segment.start),
                end=float(segment.end),
                speaker="Speaker 1",
                text=segment.text.strip(),
            )
            for index, segment in enumerate(raw_segments, start=1)
            if segment.text.strip()
        ]
        del model
        gc.collect()
        if device == "cuda":
            try:
                import torch

                torch.cuda.empty_cache()
            except (ImportError, RuntimeError):
                pass
    except Exception as exc:
        raise TranscriptionError(f"Local transcription failed: {exc}") from exc

    if not segments:
        raise TranscriptionError("No speech was detected in the audio")

    duration = max(segment.end for segment in segments)
    language = getattr(info, "language", None) or "unknown"
    return segments, language, duration
