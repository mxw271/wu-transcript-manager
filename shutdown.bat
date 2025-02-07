@echo off
chcp 65001 >nul
SETLOCAL ENABLEDELAYEDEXPANSION

echo 🛑 Stopping WU Transcript Manager...

:: --- Script Directory Setup --- 
cd /d "%~dp0"

:: --- Stop Frontend Server ---
echo 📌 Ensuring all React frontend processes are stopped...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3000') do (
    taskkill /F /PID %%a >nul 2>&1
    echo ✅ React frontend stopped.
) || echo ⚠️ No running frontend process found.

:: --- Stop Backend Server ---
echo 📌 Ensuring all FastAPI backend processes are stopped...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
    taskkill /F /PID %%a >nul 2>&1
    echo ✅ FastAPI backend stopped.
) || echo ⚠️ No running backend process found.

:: --- Deactivate Virtual Environment ---
if exist "backend\venv" (
    echo 📌 Ensuring Python virtual environment is properly deactivated...
    call backend\venv\Scripts\deactivate >nul 2>&1
) else (
    echo ⚠️ Virtual environment was not active.
)

echo ✅ All servers stopped successfully! You may now close this window.
pause
