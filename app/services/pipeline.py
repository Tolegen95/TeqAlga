from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from app.config import Settings
from app.models import MeetingMetadata, MeetingResult
from app.services.alignment import assign_speakers
from app.services.analysis import analyze
from app.services.audio import AUDIO_EXTENSIONS, normalize_audio
from app.services.diarization import diarize
from app.services.evidence import sanitize_report
from app.services.transcript_input import parse_text_transcript
from app.services.transcription import transcribe

ProgressCallback = Callable[[int, str], None]


def _noop_progress(_: int, __: str) -> None:
    return None


def process_meeting(
    source: Path,
    title: str,
    settings: Settings,
    *,
    num_speakers: int | None = None,
    source_filename: str | None = None,
    progress: ProgressCallback = _noop_progress,
) -> MeetingResult:
    meeting_id = uuid4().hex
    progress(5, "Подготовка файла")

    if source.suffix.lower() in AUDIO_EXTENSIONS:
        normalized = settings.uploads_dir / f"{meeting_id}.wav"
        try:
            normalize_audio(source, normalized)
            progress(20, "Локальная транскрибация")
            transcript, language, duration = transcribe(normalized, settings)
            progress(55, "Разделение спикеров")
            turns = diarize(normalized, settings, num_speakers=num_speakers)
            transcript = assign_speakers(transcript, turns)
        finally:
            normalized.unlink(missing_ok=True)
    else:
        progress(30, "Чтение готового транскрипта")
        transcript, language, duration = parse_text_transcript(source)

    progress(70, "Извлечение решений и поручений")
    raw_report = analyze(transcript, settings)
    report = sanitize_report(raw_report, transcript)

    speakers = {segment.speaker for segment in transcript}
    result = MeetingResult(
        metadata=MeetingMetadata(
            id=meeting_id,
            title=title.strip() or source.stem,
            source_filename=source_filename or source.name,
            language=language,
            duration_seconds=duration,
            timestamps_precise=source.suffix.lower() in AUDIO_EXTENSIONS,
            speaker_count=len(speakers),
            whisper_model=settings.whisper_model,
            llm_model=settings.ollama_model,
        ),
        transcript=transcript,
        report=report,
    )

    progress(90, "Сохранение локального протокола")
    settings.ensure_directories()
    destination = settings.meetings_dir / f"{meeting_id}.json"
    destination.write_text(
        json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    progress(100, "Готово")
    return result


def load_meeting(meeting_id: str, settings: Settings) -> MeetingResult:
    path = settings.meetings_dir / f"{meeting_id}.json"
    if not path.exists():
        raise FileNotFoundError(meeting_id)
    return MeetingResult.model_validate_json(path.read_text(encoding="utf-8"))
