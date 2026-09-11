from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OFFLINE_ENVIRONMENT_VARIABLES = (
    "HF_HUB_OFFLINE",
    "TRANSFORMERS_OFFLINE",
    "HF_DATASETS_OFFLINE",
)


def enable_model_downloads() -> None:
    """Ensure a previous offline app session cannot block model preparation."""
    for variable in OFFLINE_ENVIRONMENT_VARIABLES:
        os.environ.pop(variable, None)


def download_whisper(model: str, root: Path) -> None:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise SystemExit("Install requirements/ai.txt before downloading models") from exc

    root.mkdir(parents=True, exist_ok=True)
    print(f"Downloading Faster-Whisper model: {model}")
    WhisperModel(model, device="cpu", compute_type="int8", download_root=str(root))
    print("Whisper model is ready")


def download_diarization(destination: Path) -> None:
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit(
            "HF_TOKEN is required once for pyannote Community-1. "
            "Accept the model conditions and export a Hugging Face token."
        )
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise SystemExit("Install requirements/ai.txt before downloading models") from exc

    destination.parent.mkdir(parents=True, exist_ok=True)
    print("Downloading pyannote Community-1 for offline use")
    snapshot_download(
        repo_id="pyannote/speaker-diarization-community-1",
        local_dir=destination,
        token=token,
    )
    config_path = destination / "config.yaml"
    if not config_path.is_file():
        raise SystemExit(
            "Diarization download is incomplete: config.yaml was not created at "
            f"{config_path.resolve()}"
        )
    print(f"Diarization model is ready: {config_path.resolve()}")


def download_ollama(model: str) -> None:
    if shutil.which("ollama") is None:
        raise SystemExit("Ollama is not installed or not available in PATH")
    print(f"Downloading Ollama model: {model}")
    subprocess.run(["ollama", "pull", model], check=True)
    print("Ollama model is ready")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare every model for offline execution")
    parser.add_argument("--whisper", default=None, help="Example: large-v3 or small")
    parser.add_argument("--diarization", action="store_true")
    parser.add_argument("--ollama", default=None, help="Example: qwen3:8b")
    args = parser.parse_args()

    if not any((args.whisper, args.diarization, args.ollama)):
        parser.error("Choose at least one of --whisper, --diarization, or --ollama")
    enable_model_downloads()
    if args.whisper:
        download_whisper(args.whisper, PROJECT_ROOT / "models/whisper")
    if args.diarization:
        download_diarization(
            PROJECT_ROOT / "models/pyannote-speaker-diarization-community-1"
        )
    if args.ollama:
        download_ollama(args.ollama)


if __name__ == "__main__":
    main()
