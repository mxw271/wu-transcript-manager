#!/bin/bash

echo "Starting WU Transcript Manager setup..."

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# --- 1️⃣ Prerequisite Checks ---

echo "🔍 Checking required dependencies..."

# Check & Install Python 3.9+
if ! command_exists python3 || [[ $(python3 -V 2>&1 | awk '{print $2}') < "3.9" ]]; then
    echo "⚠️ Python 3.9+ not found. Installing Python..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install python@3.9
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt update && sudo apt install -y python3.9 python3.9-venv python3.9-dev
    fi
else
    echo "✅ Python 3.9+ is installed."
fi

# Check & Install Node.js (v18+)
if ! command_exists node || [[ $(node -v | sed 's/v//') < "18" ]]; then
    echo "⚠️ Node.js v18+ not found. Installing Node.js..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install node
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
        sudo apt install -y nodejs
    fi
else
    echo "✅ Node.js v18+ is installed."
fi

# Check & Install npm
if ! command_exists npm; then
    echo "⚠️ npm not found. Installing npm..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install npm
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt install -y npm
    fi
else
    echo "✅ npm is installed."
fi

# Check & Install virtualenv
if ! command_exists virtualenv; then
    echo "⚠️ virtualenv not found. Installing virtualenv..."
    python3 -m pip install --user virtualenv
else
    echo "✅ virtualenv is installed."
fi

# --- 2️⃣ Backend Setup ---

echo "🛠 Setting up the backend..."
cd backend

# Check if virtual environment exists, if not create one
if [ ! -d "venv" ]; then
  echo "📌 Creating Python virtual environment..."
  python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install Python dependencies
echo "📦 Installing backend dependencies..."
pip3 install -r requirements.txt

# Start the backend server in the background
echo "🚀 Starting the FastAPI backend..."
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &

# --- 3️⃣ Frontend Setup (Pure React) ---

echo "🎨 Setting up the frontend..."
cd ../

# Check if frontend exists, if not create a new React app
if [ ! -d "frontend" ]; then
  echo "📌 Creating a new React app..."
  npx create-react-app frontend
fi

cd frontend

# Install Node.js dependencies
echo "📦 Installing frontend dependencies..."
npm install

# Start the frontend server in the background
echo "🌐 Starting the React frontend..."
npm start &

# --- 4️⃣ Final Message ---
echo "✅ Setup complete! Access the web app at: http://localhost:3000"
