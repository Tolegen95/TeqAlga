from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

ReportLanguage = Literal["ru", "kk", "en", "auto"]


class TranscriptSegment(BaseModel):
    id: str
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    speaker: str
    text: str

    @model_validator(mode="after")
    def end_must_follow_start(self) -> TranscriptSegment:
        if self.end < self.start:
            raise ValueError("segment end must be greater than or equal to start")
        return self


class Finding(BaseModel):
    text: str
    evidence: list[str] = Field(default_factory=list)


class Topic(BaseModel):
    title: str
    summary: str
    evidence: list[str] = Field(default_factory=list)


class ActionItem(BaseModel):
    owner: str | None = None
    task: str
    due_date: str | None = None
    priority: Literal["low", "medium", "high", "not_specified"] = "not_specified"
    evidence: list[str] = Field(default_factory=list)


class MeetingReport(BaseModel):
    executive_summary: list[Finding] = Field(default_factory=list, max_length=5)
    key_facts: list[Finding] = Field(default_factory=list)
    topics: list[Topic] = Field(default_factory=list)
    decisions: list[Finding] = Field(default_factory=list)
    open_questions: list[Finding] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    risks: list[Finding] = Field(default_factory=list)


class MeetingMetadata(BaseModel):
    id: str
    title: str
    source_filename: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    language: str | None = None
    duration_seconds: float | None = None
    timestamps_precise: bool = True
    speaker_count: int = 0
    whisper_model: str
    llm_model: str
    report_language: ReportLanguage = "ru"
    offline: bool = True


class MeetingResult(BaseModel):
    metadata: MeetingMetadata
    transcript: list[TranscriptSegment]
    report: MeetingReport


class JobView(BaseModel):
    id: str
    status: Literal["queued", "running", "completed", "failed"]
    progress: int = Field(ge=0, le=100)
    stage: str
    meeting_id: str | None = None
    error: str | None = None
