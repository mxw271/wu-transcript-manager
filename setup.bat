@echo off
echo Starting WU Transcript Manager setup...

:: --- 1️⃣ Prerequisite Checks ---

echo Checking required dependencies...

:: Check Python 3.9+
python --version 2>nul | findstr /R "3\.[9-9]" >nul
if %ERRORLEVEL% NEQ 0 (
    echo ⚠️ Python 3.9+ not found. Please install Python 3.9 or later manually.
    exit /b 1
) else (
    echo ✅ Python 3.9+ is installed.
)

:: Check Node.js (v18+)
node --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ⚠️ Node.js v18+ not found. Please install Node.js from https://nodejs.org/
    exit /b 1
) else (
    echo ✅ Node.js is installed.
)

:: Check npm
npm --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ⚠️ npm not found. Please install npm manually.
    exit /b 1
) else (
    echo ✅ npm is installed.
)

:: Check virtualenv
where virtualenv >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ⚠️ virtualenv not found. Installing...
    python -m pip install --user virtualenv
) else (
    echo ✅ virtualenv is installed.
)

:: --- 2️⃣ Backend Setup ---
echo 🛠 Setting up the backend...
cd backend

:: Create virtual environment if not exists
if not exist venv (
    echo 📌 Creating Python virtual environment...
    python -m venv venv
)

:: Activate virtual environment
call venv\Scripts\activate

:: Install dependencies
echo 📦 Installing backend dependencies...
pip install -r requirements.txt

:: Start FastAPI backend in the background
echo 🚀 Starting the FastAPI backend...
start cmd /k "uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

cd ..

:: --- 3️⃣ Frontend Setup (Pure React) ---
echo 🎨 Setting up the frontend...

:: Create frontend directory if it doesn't exist
if not exist frontend (
    echo 📌 Creating a new React app...
    npx create-react-app frontend
)

cd frontend

:: Install frontend dependencies
echo 📦 Installing frontend dependencies...
npm install

:: Start React frontend in a new command window
echo 🌐 Starting the React frontend...
start cmd /k "npm start"

:: --- 4️⃣ Final Message ---
echo ✅ Setup complete! Access the web app at: http://localhost:3000
pause
