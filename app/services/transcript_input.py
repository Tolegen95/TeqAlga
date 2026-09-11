from __future__ import annotations

import re
from pathlib import Path

from app.models import TranscriptSegment

SPEAKER_LINE = re.compile(r"^([^:\n]{1,60}):\s*(.+)$")


def parse_text_transcript(path: Path) -> tuple[list[TranscriptSegment], str, float]:
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        raise ValueError("Transcript is empty")

    segments: list[TranscriptSegment] = []
    current_speaker = "Speaker 1"
    for line in (line.strip() for line in text.splitlines()):
        if not line:
            continue
        match = SPEAKER_LINE.match(line)
        if match:
            current_speaker, utterance = match.groups()
        else:
            utterance = line
        start = len(segments) * 5.0
        segments.append(
            TranscriptSegment(
                id=f"seg_{len(segments) + 1:04d}",
                start=start,
                end=start + 5.0,
                speaker=current_speaker.strip(),
                text=utterance.strip(),
            )
        )

    if not segments:
        raise ValueError("Transcript has no readable lines")
    return segments, "mixed_or_unknown", segments[-1].end

