#!/usr/bin/env bash
set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

echo "======================================================================"
echo "          finops-copilot — LOCAL NON-DOCKER STARTUP         "
echo "======================================================================"

# 1. Load Root Environment File if present
if [ -f "$ROOT_DIR/.env" ]; then
    set -o allexport
    source "$ROOT_DIR/.env"
    set +o allexport
elif [ -f "$ROOT_DIR/.env.example" ]; then
    echo "[!] No .env found. Copying .env.example to .env..."
    cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
    set -o allexport
    source "$ROOT_DIR/.env"
    set +o allexport
fi

# Enable zero-server local database mode if PostgreSQL host is "postgres" or unreachable
export USE_LOCAL_SQLITE=true

# 2. Backend Virtual Environment & Dependencies
BACKEND_DIR="$ROOT_DIR/backend"
VENV_DIR="$BACKEND_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "[*] Creating Python virtual environment in backend/.venv..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

echo "[*] Checking backend dependencies..."
pip install -q --no-build-isolation -r "$BACKEND_DIR/requirements.txt" aiosqlite pytz pytest-env

# 3. Frontend Dependencies
FRONTEND_DIR="$ROOT_DIR/frontend"
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "[*] Installing frontend dependencies..."
    (cd "$FRONTEND_DIR" && npm install)
fi

# 4. Process Cleanup Handler
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    echo ""
    echo "[*] Stopping finops-copilot local services..."
    if [ -n "$BACKEND_PID" ]; then
        kill "$BACKEND_PID" 2>/dev/null || true
    fi
    if [ -n "$FRONTEND_PID" ]; then
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    echo "[✓] Stopped cleanly."
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# 5. Launch Backend Service
echo "[*] Starting FastAPI Backend on http://localhost:8000..."
(cd "$BACKEND_DIR" && source "$VENV_DIR/bin/activate" && uvicorn app.main:app --host 0.0.0.0 --port 8000) &
BACKEND_PID=$!

# 6. Launch Frontend Service
echo "[*] Starting Next.js Frontend on http://localhost:3000..."
(cd "$FRONTEND_DIR" && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "======================================================================"
echo "  finops-copilot is running locally!"
echo "  • Frontend:       http://localhost:3000"
echo "  • Backend API:    http://localhost:8000"
echo "  • API Docs:       http://localhost:8000/docs"
echo "  Press Ctrl+C to stop all services."
echo "======================================================================"

wait
