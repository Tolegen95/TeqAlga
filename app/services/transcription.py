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
        # Keep word timestamps instead of throwing them away. Speaker turns often
        # change in the middle of a Whisper sentence, so sentence-level alignment
        # assigns several people to one speaker. The alignment service groups these
        # words back into readable utterances after diarization.
        segments: list[TranscriptSegment] = []
        for raw_segment in raw_segments:
            words = getattr(raw_segment, "words", None) or []
            word_count_before = len(segments)
            for word in words:
                text = str(getattr(word, "word", "")).strip()
                if not text:
                    continue
                start = getattr(word, "start", None)
                end = getattr(word, "end", None)
                segments.append(
                    TranscriptSegment(
                        id=f"word_{len(segments) + 1:06d}",
                        start=float(raw_segment.start if start is None else start),
                        end=float(raw_segment.end if end is None else end),
                        speaker="Speaker 1",
                        text=text,
                    )
                )

            # Defensive fallback for engines/files that do not expose word timings.
            if len(segments) == word_count_before and raw_segment.text.strip():
                segments.append(
                    TranscriptSegment(
                        id=f"word_{len(segments) + 1:06d}",
                        start=float(raw_segment.start),
                        end=float(raw_segment.end),
                        speaker="Speaker 1",
                        text=raw_segment.text.strip(),
                    )
                )
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
