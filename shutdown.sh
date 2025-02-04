#!/bin/bash

echo "🛑 Stopping WU Transcript Manager..."

# --- 1️⃣ Stop Backend Server ---
echo "📌 Stopping FastAPI backend..."
pkill -f "uvicorn main:app" && echo "✅ FastAPI backend stopped." || echo "⚠️ No FastAPI process found."

# --- 2️⃣ Stop Frontend Server ---
echo "📌 Stopping React frontend..."
pkill -f "node .*react-scripts start" && echo "✅ React frontend stopped." || echo "⚠️ No React frontend process found."

# --- 3️⃣ Deactivate Virtual Environment ---
if [ -d "backend/venv" ]; then
  echo "📌 Deactivating Python virtual environment..."
  source backend/venv/bin/activate
  deactivate
  echo "✅ Virtual environment deactivated."
fi

echo "✅ All servers stopped successfully."
