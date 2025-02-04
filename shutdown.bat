@echo off
echo 🛑 Stopping WU Transcript Manager...

:: --- 1️⃣ Stop Backend Server ---
echo 📌 Stopping FastAPI backend...
taskkill /F /IM python.exe /T 2>nul
if %ERRORLEVEL% EQU 0 (
    echo ✅ FastAPI backend stopped.
) else (
    echo ⚠️ No FastAPI process found.
)

:: --- 2️⃣ Stop Frontend Server ---
echo 📌 Stopping React frontend...
taskkill /F /IM node.exe /T 2>nul
if %ERRORLEVEL% EQU 0 (
    echo ✅ React frontend stopped.
) else (
    echo ⚠️ No React frontend process found.
)

:: --- 3️⃣ Deactivate Virtual Environment ---
if exist backend\venv\Scripts\activate (
    echo 📌 Deactivating Python virtual environment...
    call backend\venv\Scripts\deactivate 2>nul
    echo ✅ Virtual environment deactivated.
)

echo ✅ All servers stopped successfully.
pause
