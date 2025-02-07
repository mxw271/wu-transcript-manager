#!/bin/bash

echo "🛑 Stopping WU Transcript Manager..."

# Ensure script runs in the correct directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit

# --- Stop Frontend Server ---
echo "📌 Ensuring all React frontend processes are stopped..."
lsof -ti:3000 | xargs kill && sleep 2 && echo "✅ React frontend stopped." || echo "⚠️ No running frontend process found."

# --- Stop Backend Server ---
echo "📌 Ensuring all FastAPI backend processes are stopped..."
lsof -ti:8000 | xargs kill && echo "✅ FastAPI backend stopped." || echo "⚠️ No running backend process found."

# --- Deactivate Virtual Environment ---
echo "📌 Ensuring Python virtual environment is properly deactivated..."
if [[ -n "$VIRTUAL_ENV" ]]; then
  deactivate 2>/dev/null && echo "✅ Virtual environment stopped." || echo "⚠️ Virtual environment was not active."
fi

# --- Completion Messages ---
echo "✅ All servers stopped successfully! You may now close all windows."
exec bash
