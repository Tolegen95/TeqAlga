from __future__ import annotations

from app.models import TranscriptSegment
from app.services.diarization import SpeakerTurn


def overlap_seconds(start_a: float, end_a: float, start_b: float, end_b: float) -> float:
    return max(0.0, min(end_a, end_b) - max(start_a, start_b))


def assign_speakers(
    transcript: list[TranscriptSegment], turns: list[SpeakerTurn]
) -> list[TranscriptSegment]:
    if not turns:
        return transcript

    aligned: list[TranscriptSegment] = []
    for segment in transcript:
        best_turn = max(
            turns,
            key=lambda turn: (
                overlap_seconds(segment.start, segment.end, turn.start, turn.end),
                -abs(((segment.start + segment.end) / 2) - ((turn.start + turn.end) / 2)),
            ),
        )
        aligned.append(segment.model_copy(update={"speaker": best_turn.speaker}))
    return aligned

