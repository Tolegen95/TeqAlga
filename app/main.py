from __future__ import annotations

import shutil
import urllib.error
import urllib.request
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.jobs import job_store
from app.models import JobView, MeetingResult, ReportLanguage
from app.services.audio import AudioPreparationError, ensure_supported
from app.services.exports import export_result
from app.services.pipeline import load_meeting, process_meeting

settings = get_settings()
settings.ensure_directories()
static_dir = Path(__file__).parent / "static"

app = FastAPI(
    title=settings.app_name,
    description="Offline-first meeting transcription and structured protocol service",
    version="0.1.0",
)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/api/health")
def health() -> dict[str, object]:
    ollama_ready = False
    try:
        with urllib.request.urlopen(
            f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=1.5
        ):
            ollama_ready = True
    except (urllib.error.URLError, TimeoutError):
        pass

    return {
        "status": "ok",
        "offline": True,
        "ffmpeg": shutil.which("ffmpeg") is not None,
        "ollama": ollama_ready,
        "ollama_model": settings.ollama_model,
        "diarization_model": (
            settings.diarization_model_path / "config.yaml"
        ).is_file(),
    }


def _run_job(
    job_id: str,
    source: Path,
    source_filename: str,
    title: str,
    num_speakers: int | None,
    report_language: ReportLanguage,
) -> None:
    try:
        job_store.update(job_id, status="running", progress=1, stage="Запуск")

        def update(progress: int, stage: str) -> None:
            job_store.update(job_id, progress=progress, stage=stage)

        result = process_meeting(
            source,
            title,
            settings,
            num_speakers=num_speakers,
            report_language=report_language,
            source_filename=source_filename,
            progress=update,
        )
        job_store.update(
            job_id,
            status="completed",
            progress=100,
            stage="Готово",
            meeting_id=result.metadata.id,
        )
    except Exception as exc:
        job_store.update(
            job_id,
            status="failed",
            stage="Ошибка обработки",
            error=str(exc),
        )
    finally:
        source.unlink(missing_ok=True)


@app.post("/api/v1/meetings", response_model=JobView, status_code=202)
def create_meeting(
    background_tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form()] = "",
    num_speakers: Annotated[int | None, Form(ge=1, le=20)] = None,
    report_language: Annotated[ReportLanguage, Form()] = "ru",
) -> JobView:
    source_filename = Path(file.filename or "meeting").name
    suffix = Path(source_filename).suffix.lower()
    try:
        ensure_supported(Path(f"input{suffix}"))
    except AudioPreparationError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc

    destination = settings.uploads_dir / f"{uuid4().hex}{suffix}"
    with destination.open("wb") as stream:
        shutil.copyfileobj(file.file, stream)

    job = job_store.create()
    background_tasks.add_task(
        _run_job,
        job.id,
        destination,
        source_filename,
        title or Path(source_filename).stem,
        num_speakers,
        report_language,
    )
    return job


@app.get("/api/v1/jobs/{job_id}", response_model=JobView)
def get_job(job_id: str) -> JobView:
    try:
        return job_store.view(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc


@app.get("/api/v1/meetings/{meeting_id}", response_model=MeetingResult)
def get_meeting(meeting_id: str) -> MeetingResult:
    try:
        return load_meeting(meeting_id, settings)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Meeting not found") from exc


@app.get("/api/v1/meetings/{meeting_id}/export/{file_format}")
def download_export(meeting_id: str, file_format: str) -> FileResponse:
    if file_format not in {"json", "csv", "pdf"}:
        raise HTTPException(status_code=400, detail="Format must be json, csv, or pdf")
    try:
        result = load_meeting(meeting_id, settings)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Meeting not found") from exc

    destination = settings.exports_dir / f"{meeting_id}.{file_format}"
    export_result(result, destination, file_format)
    media_types = {
        "json": "application/json",
        "csv": "text/csv; charset=utf-8",
        "pdf": "application/pdf",
    }
    safe_title = "".join(
        character if character.isalnum() or character in {"-", "_"} else "_"
        for character in result.metadata.title
    ).strip("_")[:80] or "meeting-report"
    return FileResponse(
        destination,
        filename=f"{safe_title}.{file_format}",
        media_type=media_types[file_format],
    )
