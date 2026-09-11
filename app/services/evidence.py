from __future__ import annotations

from app.models import ActionItem, Finding, MeetingReport, Topic, TranscriptSegment


def _valid_ids(evidence: list[str], allowed: set[str]) -> list[str]:
    return list(dict.fromkeys(item for item in evidence if item in allowed))


def sanitize_report(report: MeetingReport, transcript: list[TranscriptSegment]) -> MeetingReport:
    """Remove unsupported claims and invalid references from model output."""
    allowed = {segment.id for segment in transcript}

    def findings(items: list[Finding]) -> list[Finding]:
        result: list[Finding] = []
        for item in items:
            evidence = _valid_ids(item.evidence, allowed)
            if item.text.strip() and evidence:
                result.append(item.model_copy(update={"evidence": evidence}))
        return result

    topics: list[Topic] = []
    for topic in report.topics:
        evidence = _valid_ids(topic.evidence, allowed)
        if topic.title.strip() and topic.summary.strip() and evidence:
            topics.append(topic.model_copy(update={"evidence": evidence}))

    action_items: list[ActionItem] = []
    for item in report.action_items:
        evidence = _valid_ids(item.evidence, allowed)
        if item.task.strip() and evidence:
            action_items.append(item.model_copy(update={"evidence": evidence}))

    return MeetingReport(
        executive_summary=findings(report.executive_summary)[:5],
        key_facts=findings(report.key_facts),
        topics=topics,
        decisions=findings(report.decisions),
        open_questions=findings(report.open_questions),
        action_items=action_items,
        risks=findings(report.risks),
    )

