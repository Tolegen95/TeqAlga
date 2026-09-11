from __future__ import annotations

import gc
import wave
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


def _load_normalized_wav(audio_path: Path, torch: object) -> dict[str, object]:
    """Load our 16-bit PCM WAV without relying on TorchCodec on Windows."""
    try:
        import numpy as np

        with wave.open(str(audio_path), "rb") as stream:
            channels = stream.getnchannels()
            sample_width = stream.getsampwidth()
            sample_rate = stream.getframerate()
            frames = stream.readframes(stream.getnframes())
        if sample_width != 2:
            raise ValueError(f"expected 16-bit PCM, got {sample_width * 8}-bit audio")

        samples = np.frombuffer(frames, dtype="<i2").astype("float32") / 32768.0
        if channels > 1:
            samples = samples.reshape(-1, channels).mean(axis=1)
        waveform = torch.from_numpy(samples).unsqueeze(0)
        return {"waveform": waveform, "sample_rate": sample_rate}
    except Exception as exc:
        raise DiarizationError(f"Cannot load normalized WAV for diarization: {exc}") from exc


def diarize(
    audio_path: Path,
    settings: Settings,
    num_speakers: int | None = None,
) -> list[SpeakerTurn]:
    if not settings.diarization_enabled:
        return []
    config_path = settings.diarization_model_path / "config.yaml"
    if not config_path.is_file():
        raise DiarizationError(
            "Local pyannote model is missing or incomplete: config.yaml was not found "
            f"at {config_path.resolve()}. Run scripts/download_models.py --diarization "
            "from the updated repository."
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
        # Passing an in-memory waveform avoids TorchCodec/FFmpeg DLL failures that
        # are common on Windows. The file has already been normalized to PCM WAV.
        waveform = _load_normalized_wav(audio_path, torch)
        output = pipeline(waveform, **kwargs)
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
