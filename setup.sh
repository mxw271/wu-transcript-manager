#!/bin/bash

# --- Fail Fast Configuration ---
set -eo pipefail

echo "🔄 Setting Up WU Transcript Manager..."

# --- Script Directory Setup ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit
echo "📍 Running in: $SCRIPT_DIR"

# --- Shell Configuration Detection ---
SHELL_CONFIG="$HOME/.bashrc"
if [[ "$SHELL" == *"zsh"* ]]; then
  SHELL_CONFIG="$HOME/.zshrc"
fi

# --- Dependency Checks ---
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

echo "🔍 Checking dependencies..."

# Package manager
if [[ "$OSTYPE" == "darwin"* ]]; then
  if ! command_exists brew; then
    echo "⚠️ Homebrew missing. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$SHELL_CONFIG"
    eval "$(/opt/homebrew/bin/brew shellenv)"
  else 
    echo "✅ Homebrew already installed."
    brew update && brew upgrade
  fi
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
  if ! command_exists apt; then
    echo "❌ apt missing. This script requires a Debian-based Linux distribution."
    exit 1
  else 
    echo "✅ apt already installed."
    sudo apt update && sudo apt upgrade -y
  fi
fi

# Python 3.9+
if ! command -v python3 >/dev/null 2>&1 || ! python3 -c "import sys; exit(0 if sys.version_info >= (3,9) else 1)"; then
  echo "⚠️ Python 3.9+ missing or outdated. Installing..."
  if [[ "$OSTYPE" == "darwin"* ]]; then
    brew install python
  elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sudo apt install -y python3 python3-pip 
  fi
else
  echo "✅ Python $(python3 -V | awk '{print $2}') detected."
fi

# virtualenv
if ! command -v virtualenv >/dev/null; then
  echo "⚠️ virtualenv missing. Installing..."
  if [[ "$OSTYPE" == "darwin"* ]]; then
    brew install virtualenv
  elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sudo apt install -y python3-venv
  fi
else
  echo "✅ virtualenv already installed."
fi

# Node.js v18+
if ! command_exists node || [[ $(node -v | sed 's/v//') < "18" ]]; then
  echo "⚠️ Node.js v18+ missing or outdated. Installing..."
  if [[ "$OSTYPE" == "darwin"* ]]; then
    brew install node
  elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
    sudo apt install -y nodejs
  fi
else
  echo "✅ Node.js $(node -v) detected."
fi

# Tesseract
if ! command_exists tesseract; then
  echo "⚠️ Tesseract missing. Installing..."
  if [[ "$OSTYPE" == "darwin"* ]]; then
    brew install tesseract
  elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sudo apt install -y tesseract-ocr libtesseract-dev
  fi
else
  echo "✅ Tesseract detected."
fi

# --- Tesseract Configuration ---
echo "🔧 Configuring Tesseract..."

# Set TESSDATA_PREFIX based on platform
if [[ "$OSTYPE" == "darwin"* ]]; then
  TESSDATA_PATH="/opt/homebrew/share/tessdata"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
  TESSDATA_PATH="/usr/share/tesseract-ocr/4.00/tessdata"
fi

# Configure environment variables
if ! grep -q "TESSDATA_PREFIX" "$SHELL_CONFIG"; then
  echo "export TESSDATA_PREFIX=\"$TESSDATA_PATH\"" >> "$SHELL_CONFIG"
fi
export TESSDATA_PREFIX="$TESSDATA_PATH"

# Verify Tesseract installation
echo "🔍 Verifying Tesseract installation..."
tesseract --version || { echo "❌ Tesseract verification failed"; exit 1; }

# --- Database Folder Setup ---
if [ ! -d "$SCRIPT_DIR/database" ]; then
  echo "❌ Database folder missing. Creating..."
  mkdir "$SCRIPT_DIR/database"
else
  echo "✅ Database folder exists."
fi

# --- Backend Setup ---
echo "🛠  Setting up backend..."

# Backend directory
if [ ! -d "$SCRIPT_DIR/backend" ]; then
  echo "❌ Backend folder missing. Creating..."
  mkdir "$SCRIPT_DIR/backend"
fi
cd "$SCRIPT_DIR/backend" || exit

# Create virtual environment
if [ ! -d "venv" ]; then
  echo "📌 Creating Python virtual environment..."
  python3 -m venv venv
else
  echo "✅ Python virtual environment exists."
fi

# Activate virtual environment
source venv/bin/activate
echo "✅ Virtual environment activated."

# Python dependencies
echo "📦 Installing backend dependencies..."
pip3 install --upgrade pip
if [ -f "requirements.txt" ]; then
  PYTHON_DEPS=($(awk -F'=' '{print $1}' requirements.txt))
  
  for dep in "${PYTHON_DEPS[@]}"; do
    if ! pip show "$dep" &> /dev/null; then
      echo "⚠️ $dep missing. Installing..."
      pip install "$dep"
    else
      echo "$dep already installed."
    fi
  done
else
  echo "❌ No requirements.txt found. Skipping dependency installation."
fi

# --- Frontend Setup ---
echo "🛠  Setting up frontend..."

# React app
if [ ! -d "$SCRIPT_DIR/frontend" ]; then
  echo "📌 Creating React app..."
  npx create-react-app frontend
else
  echo "✅ Frontend exists."
fi
cd "$SCRIPT_DIR/frontend" || exit

# Frontend dependencies
echo "📦 Installing frontend dependencies..."
chmod -R 755 "$SCRIPT_DIR/frontend"
npm install --legacy-peer-deps || { echo "❌ Failed to install dependencies."; exit 1; }

# --- Completion Messages ---
# Deactivate virtual environment
deactivate

echo "✅ Setup complete! Run './start.sh' to start the servers."
echo "You may now close this window."
exec bash
