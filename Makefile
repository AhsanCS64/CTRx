# Makefile for CTRx project

.PHONY: setup install-backend install-frontend run-backend run-frontend seed test lint jobs-expire jobs-retry-pdfs

setup: install-backend install-frontend

install-backend:
	cd backend && pip install -e ".[dev]"

install-frontend:
	cd frontend && npm install

run-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-frontend:
	cd frontend && npm run dev

seed:
	cd backend && python -m app.scripts.seed

test:
	cd backend && python -m pytest -q tests/ && cd ../frontend && npm test

lint:
	cd backend && ruff check . && mypy app/ && cd ../frontend && npx eslint src/ && npx tsc --noEmit

jobs-expire:
	cd backend && python -m app.jobs.run expire_viewings

jobs-retry-pdfs:
	cd backend && python -m app.jobs.run retry_pdfs
