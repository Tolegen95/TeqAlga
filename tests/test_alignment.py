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


def test_splits_one_whisper_sentence_when_speaker_changes() -> None:
    transcript = [
        TranscriptSegment(id="word_1", start=0.0, end=0.5, speaker="Unknown", text="Мы"),
        TranscriptSegment(
            id="word_2", start=0.5, end=1.0, speaker="Unknown", text="начинаем."
        ),
        TranscriptSegment(id="word_3", start=1.1, end=1.5, speaker="Unknown", text="Нет,"),
        TranscriptSegment(
            id="word_4", start=1.5, end=2.0, speaker="Unknown", text="подождите."
        ),
    ]
    turns = [
        SpeakerTurn(start=0.0, end=1.05, speaker="Speaker 1"),
        SpeakerTurn(start=1.05, end=2.1, speaker="Speaker 2"),
    ]

    result = assign_speakers(transcript, turns)

    assert [item.speaker for item in result] == ["Speaker 1", "Speaker 2"]
    assert [item.text for item in result] == ["Мы начинаем.", "Нет, подождите."]
    assert [item.id for item in result] == ["seg_0001", "seg_0002"]


def test_smooths_one_isolated_speaker_word() -> None:
    transcript = [
        TranscriptSegment(id="word_1", start=0, end=0.4, speaker="Speaker 1", text="Это"),
        TranscriptSegment(id="word_2", start=0.4, end=0.7, speaker="Speaker 2", text="наш"),
        TranscriptSegment(
            id="word_3", start=0.7, end=1.2, speaker="Speaker 1", text="проект."
        ),
    ]

    smoothed = assign_speakers(
        transcript,
        [
            SpeakerTurn(start=0, end=0.4, speaker="Speaker 1"),
            SpeakerTurn(start=0.4, end=0.7, speaker="Speaker 2"),
            SpeakerTurn(start=0.7, end=1.2, speaker="Speaker 1"),
        ],
    )
    assert len(smoothed) == 1
    assert smoothed[0].speaker == "Speaker 1"
    assert smoothed[0].text == "Это наш проект."
