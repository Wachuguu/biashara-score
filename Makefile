.PHONY: all test test-backend test-frontend lint build dev-backend dev-frontend check

VENV_PY = ./venv/bin/python
VENV_PYTEST = ./venv/bin/pytest

all: check

# Single-command verification loop (Stage 4 of AI-Native SDLC)
test-backend:
	PYTHONPATH=. $(VENV_PYTEST) backend/tests

test-frontend:
	cd frontend && npm run typecheck && npm run lint

test: test-backend test-frontend

lint:
	cd frontend && npm run lint
	PYTHONPATH=. $(VENV_PY) -m py_compile backend/src/core/*.py backend/src/wrappers/*.py backend/local_server.py

build:
	cd frontend && npm run build

check: test lint
	@echo "All tests, typechecks, and lints passed cleanly!"

dev-backend:
	PYTHONPATH=. $(VENV_PY) backend/local_server.py

dev-frontend:
	cd frontend && npm run dev
