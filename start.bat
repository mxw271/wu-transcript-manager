@echo off
chcp 65001 >nul
SETLOCAL ENABLEDELAYEDEXPANSION

echo "🚀 Starting WU Transcript Manager..."

:: --- Script Directory Setup --- 
cd /d "%~dp0"

:: --- Activate Virtual Environment ---
echo 🌐 Activating Python virtual environment...
call backend\venv\Scripts\activate

:: --- Start Backend Server ---
echo 🌐 Starting FastAPI backend...
start cmd /k "cd backend && call venv\Scripts\activate && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

:: --- Start Frontend Server --- 
echo 🌐 Starting React frontend...
start cmd /k "cd frontend && npm start"

:: --- Completion Messages ---
echo 🚀 Servers are running! Access the web app at: http://localhost:3000
echo 🔄 Leave this window open.
echo 🛑 To stop everything, run: './shutdown.sh' or press Ctrl + C to exit manually.

# Keep the window open
pause