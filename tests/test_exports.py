import csv
import json
from pathlib import Path

from app.models import ActionItem, MeetingMetadata, MeetingReport, MeetingResult
from app.services.exports import export_csv, export_json


def sample_result() -> MeetingResult:
    return MeetingResult(
        metadata=MeetingMetadata(
            id="demo",
            title="Встреча",
            source_filename="meeting.txt",
            whisper_model="large-v3",
            llm_model="qwen3:8b",
        ),
        transcript=[],
        report=MeetingReport(
            action_items=[
                ActionItem(
                    owner="Мария",
                    task="Подготовить макет",
                    due_date="пятница",
                    priority="high",
                    evidence=["seg_0001"],
                )
            ]
        ),
    )


def test_json_export_is_utf8(tmp_path: Path) -> None:
    destination = export_json(sample_result(), tmp_path / "result.json")
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["report"]["action_items"][0]["owner"] == "Мария"


def test_csv_export_contains_action_items(tmp_path: Path) -> None:
    destination = export_csv(sample_result(), tmp_path / "actions.csv")
    with destination.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["task"] == "Подготовить макет"

