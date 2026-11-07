#!/bin/bash
# Stop old instances on ports 8000 and 3000
echo "Clearing ports 8000 and 3000..."
kill -9 $(lsof -ti:8000) 2>/dev/null
kill -9 $(lsof -ti:3000) 2>/dev/null

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cleanup() {
  echo ""
  echo "Shutting down servers..."
  kill $(jobs -p) 2>/dev/null
  exit
}
trap cleanup SIGINT SIGTERM EXIT

echo "Starting FastAPI Backend on http://127.0.0.1:8000..."
cd "$PROJECT_DIR"
./.venv/bin/uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

echo "Starting Next.js Frontend on http://localhost:3000..."
cd "$PROJECT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "=================================================="
echo "🚀 Code Review Agent is running!"
echo "   Web Dashboard: http://localhost:3000"
echo "   Backend Docs:  http://127.0.0.1:8000/docs"
echo "Press Ctrl+C to stop both servers."
echo "=================================================="
echo ""

wait

