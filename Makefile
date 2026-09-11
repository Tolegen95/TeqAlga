.PHONY: install install-ai run test lint prepare-models

install:
	python -m pip install -r requirements/base.txt

install-ai:
	python -m pip install -r requirements/ai.txt

run:
	uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

test:
	python -m pytest

lint:
	ruff check app tests scripts

prepare-models:
	python scripts/download_models.py --whisper large-v3 --diarization

