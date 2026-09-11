from __future__ import annotations

import json
import urllib.error
import urllib.request

from app.config import Settings
from app.models import MeetingReport, ReportLanguage, TranscriptSegment


class AnalysisError(RuntimeError):
    pass


LANGUAGE_NAMES: dict[ReportLanguage, str] = {
    "ru": "Russian",
    "kk": "Kazakh",
    "en": "English",
    "auto": "the dominant language of the transcript",
}


def _system_prompt(report_language: ReportLanguage) -> str:
    language = LANGUAGE_NAMES[report_language]
    return f"""You are a precise meeting protocol assistant.
Analyze only the supplied transcript. Never invent names, owners, deadlines,
decisions, risks, or facts. Every output item must reference one or more valid
segment IDs in its evidence field. If information was not explicitly stated,
use null or omit the item.

LANGUAGE REQUIREMENT: Write every human-readable output value in {language}.
This includes every text, title, summary, owner, task, due_date, and risk value.
Preserve personal names, product names, evidence IDs, and explicitly spoken dates.
Do not switch to English merely because the JSON field names are in English.

Return only data matching the provided JSON schema.
"""


def _transcript_payload(segments: list[TranscriptSegment]) -> str:
    rows = [
        {
            "id": segment.id,
            "start": round(segment.start, 2),
            "end": round(segment.end, 2),
            "speaker": segment.speaker,
            "text": segment.text,
        }
        for segment in segments
    ]
    return json.dumps(rows, ensure_ascii=False)


def analyze(
    segments: list[TranscriptSegment],
    settings: Settings,
    report_language: ReportLanguage = "ru",
) -> MeetingReport:
    transcript_json = _transcript_payload(segments)
    if len(transcript_json) > settings.max_transcript_chars:
        raise AnalysisError(
            "Transcript is too long for the current single-pass analyzer. "
            "Increase MAX_TRANSCRIPT_CHARS or add chunked processing."
        )

    schema = MeetingReport.model_json_schema()
    prompt = f"""Create a structured meeting protocol from this transcript.

Requirements:
- executive_summary: 3 to 5 concise, important statements;
- key_facts: concrete facts explicitly spoken;
- topics: semantic blocks discussed during the meeting;
- decisions: only final agreements;
- open_questions: unresolved questions;
- action_items: owner, task, due date, and priority only when stated;
- risks: explicitly mentioned blockers, conflicts, or technical risks;
- evidence: exact segment IDs supporting each item.

TRANSCRIPT:
{transcript_json}
"""
    body = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": _system_prompt(report_language)},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "format": schema,
        "keep_alive": 0,
        "options": {"temperature": settings.llm_temperature},
    }
    request = urllib.request.Request(
        f"{settings.ollama_base_url.rstrip('/')}/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=settings.ollama_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        content = payload["message"]["content"]
        return MeetingReport.model_validate_json(content)
    except urllib.error.URLError as exc:
        raise AnalysisError(
            f"Cannot reach local Ollama at {settings.ollama_base_url}. "
            f"Start Ollama and pull {settings.ollama_model}."
        ) from exc
    except (KeyError, json.JSONDecodeError, ValueError) as exc:
        raise AnalysisError(f"Ollama returned an invalid structured response: {exc}") from exc
