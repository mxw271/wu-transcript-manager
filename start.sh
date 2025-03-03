#!/bin/bash

echo "🚀 Starting WU Transcript Manager..."

# Ensure script runs in the correct directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit

# --- Activate Virtual Environment ---
echo "🌐 Activating Python Virtual environment..."
source "$SCRIPT_DIR/backend/venv/bin/activate"

# --- Start Backend Server ---
echo "🌐 Starting FastAPI backend..."
cd "$SCRIPT_DIR/backend" || exit
if lsof -i :8000 >/dev/null 2>&1; then
  echo "⚠️ Stopping existing backend server..."
  kill -9 $(lsof -t -i :8000)
fi
uvicorn main:app --host 0.0.0.0 --port 8000 --reload & 
sleep 6

# --- Start Frontend Server --- 
echo "🌐 Starting React frontend in production mode..."
cd "$SCRIPT_DIR/frontend" || exit
if lsof -i :3000 >/dev/null 2>&1; then
  echo "⚠️ Stopping existing frontend server..."
  kill -9 $(lsof -t -i :3000)
fi
serve -s build -l 3000 & 
sleep 2

# --- Completion Messages ---
echo "🚀 Servers are running! Access the web app at: http://localhost:3000"
echo "🔄 Leave this window open."
echo "🛑 To stop everything, run: './shutdown.sh' or press Ctrl + C to exit manually." 

# Keep the window open
tail -f /dev/null