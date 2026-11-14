#!/usr/bin/env bash
# Start MandiMitra field-analysis server on http://localhost:8077
cd "$(dirname "$0")"
[ -d .venv ] || { python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt; }
. .venv/bin/activate
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8077}"
