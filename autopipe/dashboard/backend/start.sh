#!/bin/bash
cd "$(dirname "$0")"
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Start the FastAPI server
exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
