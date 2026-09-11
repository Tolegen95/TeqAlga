from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Meeting Intelligence"
    data_dir: Path = Path("data")

    whisper_model: str = "large-v3"
    whisper_device: Literal["auto", "cpu", "cuda"] = "auto"
    whisper_compute_type: str = "auto"
    whisper_download_root: Path = Path("models/whisper")

    diarization_enabled: bool = True
    diarization_model_path: Path = Path("models/pyannote-speaker-diarization-community-1")

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:8b"
    ollama_timeout_seconds: int = 300

    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_transcript_chars: int = Field(default=90_000, ge=1_000)

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def meetings_dir(self) -> Path:
        return self.data_dir / "meetings"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    def ensure_directories(self) -> None:
        for path in (self.uploads_dir, self.meetings_dir, self.exports_dir):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()

