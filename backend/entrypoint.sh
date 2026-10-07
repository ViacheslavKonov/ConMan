#!/bin/sh
set -eu
echo "[ConMan] Applying database migrations..."
alembic upgrade head
echo "[ConMan] Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
