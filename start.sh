#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Wallet Cluster Tracker — start all services
# Usage:
#   ./start.sh          → start backend + frontend (assumes ETL pipeline already ran)
#   ./start.sh --etl    → also run the ETL pipeline first
# ─────────────────────────────────────────────────────────────────────────────

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT="${BACKEND_PORT:-4000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
APP_HOST="${APP_HOST:-172.20.72.198}"

run_etl() {
  echo ""
  echo "=== Running ETL Pipeline ==="
  cd "$ROOT/AML"
  if [ ! -d "venv" ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt -q
    pip install -e . -q
  else
    source venv/bin/activate
  fi
  python -m aml_pipeline.pipelines.run_etl
  deactivate
  cd "$ROOT"
}

start_backend() {
  echo ""
  echo "=== Starting FastAPI Backend (port $BACKEND_PORT) ==="
  cd "$ROOT/crypto-aml-tracker/backend-py"
  if [ ! -d "venv" ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt -q
  else
    source venv/bin/activate
  fi
  PORT="$BACKEND_PORT" HOST="0.0.0.0" python main.py &
  BACKEND_PID=$!
  echo "Backend PID: $BACKEND_PID"
  deactivate
  cd "$ROOT"
}

start_frontend() {
  echo ""
  echo "=== Starting React Frontend (port $FRONTEND_PORT) ==="
  cd "$ROOT/crypto-aml-tracker"
  if [ ! -d "node_modules" ]; then
    npm install -q
  fi
  VITE_BACKEND_TARGET="http://127.0.0.1:$BACKEND_PORT" \
  VITE_WALLET_ANALYSIS_URL="http://$APP_HOST:3000" \
  npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT" --strictPort &
  FRONTEND_PID=$!
  echo "Frontend PID: $FRONTEND_PID"
  cd "$ROOT"
}

# ── main ──────────────────────────────────────────────────────────────────────

if [[ "$1" == "--etl" ]]; then
  run_etl
fi

start_backend
sleep 2
start_frontend

echo ""
echo "─────────────────────────────────────────────────────────────────────────"
echo "  Backend (this PC)        → http://127.0.0.1:$BACKEND_PORT"
echo "  Backend (LAN accessible) → http://$APP_HOST:$BACKEND_PORT"
echo "  Frontend (this PC)       → http://127.0.0.1:$FRONTEND_PORT"
echo "  Frontend (LAN accessible)→ http://$APP_HOST:$FRONTEND_PORT"
echo "─────────────────────────────────────────────────────────────────────────"
echo "Press Ctrl+C to stop all services."

wait
