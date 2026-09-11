from __future__ import annotations

import json
import os
import shutil
import urllib.error
import urllib.request

from app.config import get_settings

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_DATASETS_OFFLINE"] = "1"


def main() -> int:
    settings = get_settings()
    checks: list[tuple[str, bool, str]] = []
    checks.append(("FFmpeg", shutil.which("ffmpeg") is not None, "binary in PATH"))
    checks.append(
        (
            "pyannote Community-1",
            settings.diarization_model_path.exists(),
            "local model folder",
        )
    )
    checks.append(
        ("Whisper cache", settings.whisper_download_root.exists(), "local model cache")
    )

    ollama_ready = False
    ollama_models: list[str] = []
    try:
        with urllib.request.urlopen(
            f"{settings.ollama_base_url.rstrip('/')}/api/tags", timeout=2
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        ollama_models = [item.get("name", "") for item in payload.get("models", [])]
        ollama_ready = bool(ollama_models)
    except (urllib.error.URLError, json.JSONDecodeError):
        pass
    configured_model = any(model == settings.ollama_model for model in ollama_models)
    checks.append(
        (
            f"Ollama model {settings.ollama_model}",
            ollama_ready and configured_model,
            ", ".join(ollama_models) or "no local model",
        )
    )

    print("Offline readiness")
    for name, ready, detail in checks:
        print(f"[{'OK' if ready else 'MISSING'}] {name}: {detail}")
    return 0 if all(ready for _, ready, _ in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
