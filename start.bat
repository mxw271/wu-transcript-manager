@echo off
chcp 65001 >nul
SETLOCAL ENABLEDELAYEDEXPANSION

echo Starting WU Transcript Manager...

:: --- Script Directory Setup --- 
cd /d "%~dp0"

:: --- Activate Virtual Environment ---
echo Activating Python virtual environment...
call backend\venv\Scripts\activate

:: --- Start Backend Server ---
echo Starting FastAPI backend...
cd backend 
start /b uvicorn main:app --host 0.0.0.0 --port 8000 --reload
cd ..

:: --- Start Frontend Server --- 
echo Starting React frontend in production mode...
cd frontend
start /b serve -s build -l 3000
cd ..

:: --- Completion Messages ---
echo Servers are running! Access the web app at: http://localhost:3000
echo Leave this window open.
echo To stop everything, run: './shutdown.bat' or press Ctrl + C to exit manually.

:: Keep the window open
cmd /k