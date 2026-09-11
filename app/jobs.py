from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from uuid import uuid4

from app.models import JobView


@dataclass
class _Job:
    id: str
    status: str = "queued"
    progress: int = 0
    stage: str = "В очереди"
    meeting_id: str | None = None
    error: str | None = None
    lock: Lock = field(default_factory=Lock, repr=False)


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, _Job] = {}
        self._lock = Lock()

    def create(self) -> JobView:
        job = _Job(id=uuid4().hex)
        with self._lock:
            self._jobs[job.id] = job
        return self.view(job.id)

    def update(
        self,
        job_id: str,
        *,
        status: str | None = None,
        progress: int | None = None,
        stage: str | None = None,
        meeting_id: str | None = None,
        error: str | None = None,
    ) -> JobView:
        job = self._get(job_id)
        with job.lock:
            if status is not None:
                job.status = status
            if progress is not None:
                job.progress = max(0, min(100, progress))
            if stage is not None:
                job.stage = stage
            if meeting_id is not None:
                job.meeting_id = meeting_id
            if error is not None:
                job.error = error
        return self.view(job_id)

    def view(self, job_id: str) -> JobView:
        job = self._get(job_id)
        with job.lock:
            return JobView(
                id=job.id,
                status=job.status,
                progress=job.progress,
                stage=job.stage,
                meeting_id=job.meeting_id,
                error=job.error,
            )

    def _get(self, job_id: str) -> _Job:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job


job_store = JobStore()

