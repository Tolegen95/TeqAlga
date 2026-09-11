from app.models import ActionItem, Finding, MeetingReport, TranscriptSegment
from app.services.evidence import sanitize_report


def test_unsupported_findings_are_removed() -> None:
    transcript = [
        TranscriptSegment(id="seg_0001", start=0, end=3, speaker="Алия", text="Срок — пятница")
    ]
    report = MeetingReport(
        key_facts=[
            Finding(text="Срок — пятница", evidence=["seg_0001"]),
            Finding(text="Бюджет утверждён", evidence=["missing"]),
        ],
        action_items=[
            ActionItem(task="Закончить макет", owner="Мария", evidence=[]),
        ],
    )

    clean = sanitize_report(report, transcript)

    assert [item.text for item in clean.key_facts] == ["Срок — пятница"]
    assert clean.action_items == []

