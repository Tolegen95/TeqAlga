from app.models import TranscriptSegment
from app.services.alignment import assign_speakers, overlap_seconds
from app.services.diarization import SpeakerTurn


def test_overlap_seconds() -> None:
    assert overlap_seconds(0, 5, 3, 8) == 2
    assert overlap_seconds(0, 2, 3, 5) == 0


def test_assigns_speaker_with_largest_overlap() -> None:
    transcript = [
        TranscriptSegment(id="seg_0001", start=0, end=3, speaker="Unknown", text="Hello"),
        TranscriptSegment(id="seg_0002", start=3, end=6, speaker="Unknown", text="Hi"),
    ]
    turns = [
        SpeakerTurn(start=0, end=2.8, speaker="Speaker 1"),
        SpeakerTurn(start=2.8, end=6, speaker="Speaker 2"),
    ]

    result = assign_speakers(transcript, turns)

    assert [item.speaker for item in result] == ["Speaker 1", "Speaker 2"]

