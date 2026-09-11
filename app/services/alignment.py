from __future__ import annotations

import re

from app.models import TranscriptSegment
from app.services.diarization import SpeakerTurn

MAX_UTTERANCE_SECONDS = 18.0
MAX_CONTINUATION_GAP_SECONDS = 1.25
ISOLATED_WORD_MAX_SECONDS = 1.75


def _join_text(left: str, right: str) -> str:
    text = f"{left.strip()} {right.strip()}".strip()
    text = re.sub(r"\s+([,.!?;:%)\]}»…])", r"\1", text)
    text = re.sub(r"([({\[«])\s+", r"\1", text)
    return text


def overlap_seconds(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    return max(0.0, min(end_a, end_b) - max(start_a, start_b))


def assign_speakers(
    transcript: list[TranscriptSegment], turns: list[SpeakerTurn]
) -> list[TranscriptSegment]:
    if not transcript:
        return []

    aligned: list[TranscriptSegment] = []
    if turns:
        for segment in transcript:
            best_turn = max(
                turns,
                key=lambda turn: (
                    overlap_seconds(segment.start, segment.end, turn.start, turn.end),
                    -abs(
                        ((segment.start + segment.end) / 2)
                        - ((turn.start + turn.end) / 2)
                    ),
                ),
            )
            aligned.append(segment.model_copy(update={"speaker": best_turn.speaker}))
    else:
        aligned = list(transcript)

    # Remove a common diarization artifact: one short word assigned to another
    # speaker while both neighbouring words belong to the same person.
    labels = [segment.speaker for segment in aligned]
    for index in range(1, len(aligned) - 1):
        previous = labels[index - 1]
        current = labels[index]
        following = labels[index + 1]
        duration = aligned[index].end - aligned[index].start
        if previous == following and current != previous and duration <= ISOLATED_WORD_MAX_SECONDS:
            labels[index] = previous

    smoothed = [
        segment.model_copy(update={"speaker": labels[index]})
        for index, segment in enumerate(aligned)
    ]
    return merge_speaker_segments(smoothed)


def merge_speaker_segments(transcript: list[TranscriptSegment]) -> list[TranscriptSegment]:
    """Group word-level timestamps into readable, speaker-consistent utterances."""
    if not transcript:
        return []

    merged: list[TranscriptSegment] = []
    current = transcript[0].model_copy()
    for segment in transcript[1:]:
        gap = max(0.0, segment.start - current.end)
        current_duration = current.end - current.start
        same_turn = (
            segment.speaker == current.speaker
            and gap <= MAX_CONTINUATION_GAP_SECONDS
            and current_duration < MAX_UTTERANCE_SECONDS
        )
        if same_turn:
            current = current.model_copy(
                update={
                    "end": max(current.end, segment.end),
                    "text": _join_text(current.text, segment.text),
                }
            )
            continue

        merged.append(current)
        current = segment.model_copy()
    merged.append(current)

    return [
        segment.model_copy(update={"id": f"seg_{index:04d}"})
        for index, segment in enumerate(merged, start=1)
    ]
