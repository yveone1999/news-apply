PY := /Users/yangl/miniconda3/bin/python3
VENV := .venv
BIN := $(VENV)/bin

.PHONY: venv install migrate test run collect

venv:
	$(PY) -m venv $(VENV)

install:
	$(BIN)/pip install -q -U pip
	$(BIN)/pip install -q fastapi "uvicorn[standard]" sqlalchemy alembic httpx feedparser pyyaml python-dotenv pytest

migrate:
	$(BIN)/alembic -c alembic.ini upgrade head
	$(BIN)/alembic -c alembic.ini revision --autogenerate -m "$(m)"

test:
	$(BIN)/pytest -q

run:
	$(BIN)/uvicorn apps.api.main:app --host 127.0.0.1 --port 8700

start:
	./scripts/start.sh

stop:
	./scripts/stop.sh

status:
	./scripts/status.sh
