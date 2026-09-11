from pathlib import Path

from app.config import Settings
from app.models import Finding, MeetingReport
from app.services import pipeline


def test_text_pipeline_preserves_original_filename(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "stored-id.txt"
    source.write_text("Алия: Решили работать локально.", encoding="utf-8")
    settings = Settings(data_dir=tmp_path / "data")
    monkeypatch.setattr(
        pipeline,
        "analyze",
        lambda segments, _, report_language: MeetingReport(
            decisions=[Finding(text="Работать локально", evidence=[segments[0].id])]
        ),
    )

    result = pipeline.process_meeting(
        source,
        "Планирование",
        settings,
        source_filename="original.txt",
    )

    assert result.metadata.source_filename == "original.txt"
    assert result.metadata.timestamps_precise is False
    assert result.metadata.report_language == "ru"
    assert result.report.decisions[0].text == "Работать локально"
    assert (settings.meetings_dir / f"{result.metadata.id}.json").exists()
