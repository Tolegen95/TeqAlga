from __future__ import annotations

import gc
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings


@dataclass(frozen=True)
class SpeakerTurn:
    start: float
    end: float
    speaker: str


class DiarizationError(RuntimeError):
    pass


def diarize(
    audio_path: Path,
    settings: Settings,
    num_speakers: int | None = None,
) -> list[SpeakerTurn]:
    if not settings.diarization_enabled:
        return []
    if not settings.diarization_model_path.exists():
        raise DiarizationError(
            "Local pyannote model not found. Run scripts/download_models.py first."
        )

    try:
        import torch
        from pyannote.audio import Pipeline
    except ImportError as exc:
        raise DiarizationError(
            "pyannote.audio is missing. Install requirements/ai.txt first."
        ) from exc

    try:
        pipeline = Pipeline.from_pretrained(str(settings.diarization_model_path))
        if torch.cuda.is_available():
            pipeline.to(torch.device("cuda"))

        kwargs = {"num_speakers": num_speakers} if num_speakers else {}
        output = pipeline(str(audio_path), **kwargs)
        annotation = getattr(output, "exclusive_speaker_diarization", None)
        if annotation is None:
            annotation = getattr(output, "speaker_diarization", output)

        labels: dict[str, str] = {}
        turns: list[SpeakerTurn] = []
        for turn, _, raw_speaker in annotation.itertracks(yield_label=True):
            label = labels.setdefault(raw_speaker, f"Speaker {len(labels) + 1}")
            turns.append(SpeakerTurn(float(turn.start), float(turn.end), label))
        del pipeline, output
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return turns
    except Exception as exc:
        raise DiarizationError(f"Local speaker diarization failed: {exc}") from exc
