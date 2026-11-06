#!/usr/bin/env bash
# Aegis AI - one-command start (POSIX).
# 1. ensures a venv with pinned deps   2. kills any stale server on :8000
# 3. runs alembic migrations           4. serves API+PWA on 127.0.0.1:8000
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  echo "[aegis] creating venv..."
  python3.13 -m venv .venv || python3 -m venv .venv
  echo "[aegis] installing pinned dependencies..."
  .venv/bin/python -m pip install --upgrade pip >/dev/null
  .venv/bin/python -m pip install -r requirements-server.txt
fi

# kill anything already holding the port
pid=$(lsof -ti :8000 2>/dev/null || true)
if [ -n "${pid}" ]; then
  echo "[aegis] stopping stale process ${pid} on port 8000"
  kill "${pid}" 2>/dev/null || true
  sleep 1
fi

echo "[aegis] running database migrations..."
.venv/bin/python -m alembic upgrade head

echo "[aegis] starting on http://127.0.0.1:8000  (Ctrl+C to stop)"
exec .venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
