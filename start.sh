#!/bin/bash
# PRIVEX — Start backend + frontend together
set -e

echo ""
echo "  ██████╗ ██████╗ ██╗██╗   ██╗███████╗██╗  ██╗"
echo "  ██╔══██╗██╔══██╗██║██║   ██║██╔════╝╚██╗██╔╝"
echo "  ██████╔╝██████╔╝██║██║   ██║█████╗   ╚███╔╝ "
echo "  ██╔═══╝ ██╔══██╗██║╚██╗ ██╔╝██╔══╝   ██╔██╗ "
echo "  ██║     ██║  ██║██║ ╚████╔╝ ███████╗██╔╝ ██╗"
echo "  ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝"
echo "  AI Privacy Firewall — Local-First"
echo ""

# ── Backend ──────────────────────────────────────────────────────────────────
echo "[1/2] Starting FastAPI backend on http://localhost:8000 ..."
cd "$(dirname "$0")/backend"

if [ ! -d ".venv" ]; then
  echo "      Creating virtualenv..."
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -q -r requirements.txt
else
  source .venv/bin/activate
fi

uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo "      Backend PID: $BACKEND_PID"

# ── Frontend ─────────────────────────────────────────────────────────────────
echo "[2/2] Starting React frontend on http://localhost:5173 ..."
cd "$(dirname "$0")/frontend"

if [ ! -d "node_modules" ]; then
  echo "      Installing npm packages..."
  npm install --silent
fi

npm run dev &
FRONTEND_PID=$!
echo "      Frontend PID: $FRONTEND_PID"

echo ""
echo "  ✓ Backend:  http://localhost:8000"
echo "  ✓ Frontend: http://localhost:5173"
echo "  ✓ API Docs: http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop both servers."
echo ""

# Cleanup on exit
trap "echo 'Stopping...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
