@echo off
chcp 65001 >nul
SETLOCAL ENABLEDELAYEDEXPANSION

echo 🔄 Setting Up WU Transcript Manager...

:: --- Script Directory Setup --- 
cd /d "%~dp0"
echo 📍 Running in: %CD%

:: --- Dependency Checks ---
echo 🔍 Checking dependencies...

:: Python 3.9+
python --version 2>nul | findstr /R "3\.[9-9]" >nul
if %ERRORLEVEL% NEQ 0 (
    echo ⚠️ Python 3.9+ missing or outdated. Installing...
    curl -O https://www.python.org/ftp/python/3.13.2/python-3.13.2-amd64.exe
    start /wait python-3.13.2-amd64.exe /quiet InstallAllUsers=1 PrependPath=1
    del python-3.13.2-amd64.exe
) else (
    echo ✅ Python detected: 
    python --version
)

:: virtualenv
python -m virtualenv --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ⚠️ virtualenv missing. Installing...
    python3 -m pip install --user virtualenv
) else (
    echo ✅ virtualenv already exists.
)

:: Node.js (v18+)
node --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ⚠️ Node.js v18+ missing or outdated. Installing...
    curl -O https://nodejs.org/dist/v18.17.1/node-v18.17.1-x64.msi
    start /wait msiexec /i node-v18.17.1-x64.msi /quiet
    del node-v18.17.1-x64.msi
) else (
    echo ✅ Node.js detected: 
    node -v
)

:: Tesseract
where tesseract >nul 2>nul
if %errorlevel% neq 0 (
    echo ⚠️ Tesseract missing. Installing...
    curl -O https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.3.0.20221222.exe
    start /wait tesseract-ocr-w64-setup-5.3.0.20221222.exe /quiet
    del tesseract-ocr-w64-setup-5.3.0.20221222.exe
) else (
    echo ✅ Tesseract detected:
    tesseract --version
)

:: Set TESSDATA_PREFIX
setx TESSDATA_PREFIX "C:\Program Files\Tesseract-OCR\tessdata"

:: ---- Database Folder Setup ----
if not exist "database" (
    echo ❌ Database folder missing. Creating...
    mkdir database
) else (
    echo ✅ Database folder exists.
)

:: --- Backend Setup ---
echo 🛠 Setting up the backend...
if not exist "backend" mkdir backend
cd backend

:: Create virtual environment
if not exist venv (
    echo 📌 Creating Python virtual environment...
    python -m venv venv
)

:: Activate virtual environment
call venv\Scripts\activate
echo ✅ Virtual environment activated.

:: Install dependencies
echo 📦 Installing backend dependencies...
if exist "requirements.txt" (
    echo 📦 Installing backend dependencies...
    pip install --upgrade pip
    pip install -r requirements.txt
) else (
    echo ❌ No requirements.txt found. Skipping dependency installation.
)

cd ..

:: --- Frontend Setup (Pure React) ---
echo 🎨 Setting up the frontend...

:: Create frontend directory if it doesn't exist
if not exist frontend (
    echo 📌 Creating React app...
    npx create-react-app frontend
)
cd frontend

:: Install frontend dependencies
echo 📦 Installing frontend dependencies...
npm install --legacy-peer-deps

cd ..

:: --- Completion Messages ---
:: Deactivate virtual environment
call backend\venv\Scripts\deactivate >nul 2>&1

echo ✅ Setup complete! Run './start.sh' to start the servers.
echo You may now close this window.
pause
