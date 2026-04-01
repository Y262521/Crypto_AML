#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Crypto AML Tracker — start all services
# Usage:
#   ./start.sh          → start backend + frontend (assumes AML pipeline already ran)
#   ./start.sh --etl    → also run the AML ETL pipeline first
# ─────────────────────────────────────────────────────────────────────────────

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

run_etl() {
  echo ""
  echo "=== Running AML ETL Pipeline ==="
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
  echo "=== Starting FastAPI Backend (port 4000) ==="
  cd "$ROOT/crypto-aml-tracker/backend-py"
  if [ ! -d "venv" ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt -q
  else
    source venv/bin/activate
  fi
  python main.py &
  BACKEND_PID=$!
  echo "Backend PID: $BACKEND_PID"
  deactivate
  cd "$ROOT"
}

start_frontend() {
  echo ""
  echo "=== Starting React Frontend (port 5173) ==="
  cd "$ROOT/crypto-aml-tracker"
  if [ ! -d "node_modules" ]; then
    npm install -q
  fi
  npm run dev &
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
echo "  Backend  → http://localhost:4000"
echo "  Frontend → http://localhost:5173" 
echo "─────────────────────────────────────────────────────────────────────────"
echo "Press Ctrl+C to stop all services."

wait
