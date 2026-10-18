#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"
PYTHON_BIN="${PYTHON_BIN:-python3.12}"
"$PYTHON_BIN" scripts/init_env.py
if [ ! -d backend/.venv ]; then "$PYTHON_BIN" -m venv backend/.venv; fi
backend/.venv/bin/pip install -q -r backend/requirements.txt
(cd frontend && npm ci --no-fund)
BACKEND_PID=""
FRONTEND_PID=""
cleanup() {
  if [ -n "$BACKEND_PID" ]; then kill "$BACKEND_PID" 2>/dev/null || true; fi
  if [ -n "$FRONTEND_PID" ]; then kill "$FRONTEND_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT INT TERM
(cd backend && exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000) &
BACKEND_PID=$!
(cd frontend && exec npm run dev) &
FRONTEND_PID=$!
echo "Starting frontend at http://localhost:3000 and API at http://localhost:8000."
echo "Use local .env credentials. Startup errors remain visible in this terminal."
wait -n "$BACKEND_PID" "$FRONTEND_PID"
