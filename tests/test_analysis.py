import json
from typing import Self

from app.config import Settings
from app.models import TranscriptSegment
from app.services import analysis


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


def test_analyzer_requests_grounded_structured_output(monkeypatch) -> None:
    captured: dict = {}
    model_output = {
        "executive_summary": [{"text": "Решение принято", "evidence": ["seg_0001"]}],
        "key_facts": [],
        "topics": [],
        "decisions": [],
        "open_questions": [],
        "action_items": [],
        "risks": [],
    }

    def fake_urlopen(request, timeout):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse({"message": {"content": json.dumps(model_output)}})

    monkeypatch.setattr(analysis.urllib.request, "urlopen", fake_urlopen)
    transcript = [
        TranscriptSegment(
            id="seg_0001", start=0, end=2, speaker="Speaker 1", text="Решение принято"
        )
    ]

    result = analysis.analyze(transcript, Settings(ollama_model="qwen3:4b"))

    assert result.executive_summary[0].evidence == ["seg_0001"]
    assert captured["body"]["model"] == "qwen3:4b"
    assert captured["body"]["keep_alive"] == 0
    assert captured["body"]["format"]["title"] == "MeetingReport"
