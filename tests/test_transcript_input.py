from pathlib import Path

from app.services.transcript_input import parse_text_transcript


def test_parses_named_speakers(tmp_path: Path) -> None:
    source = tmp_path / "meeting.txt"
    source.write_text("Алия: Начинаем.\nМария: Согласна.", encoding="utf-8")

    segments, language, duration = parse_text_transcript(source)

    assert [segment.speaker for segment in segments] == ["Алия", "Мария"]
    assert [segment.id for segment in segments] == ["seg_0001", "seg_0002"]
    assert language == "mixed_or_unknown"
    assert duration == 10.0

