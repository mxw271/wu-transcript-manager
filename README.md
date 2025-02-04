# WU Transcript Manager

## Overview
This project is a **full-stack web application** for managing and categorizing transcripts. It consists of:
- **Backend**: FastAPI (Python) with SQLite database
- **Frontend**: React (Create React App)
- **Machine Learning**: SBERT & OpenAI API for text processing

---

## Setup Instructions

### **Prerequisites**
Ensure you have the following installed:
- **Python 3.9+**
- **Node.js (v18+)**
- **npm (comes with Node.js)**
- **virtualenv** (for Python)

If missing, the setup script will attempt to install them automatically.

### **Quick Start**
1️⃣ **Clone the repository**:
```sh
git clone https://github.com/mxw271/wu-transcript-manager.git
cd wu-transcript-manager
```

2️⃣ **API Key Configuration**:  

**🔑 Update your API keys** in the `backend/.env` file.  

Navigate to the `backend/` folder and create a `.env` file if it doesn’t exist:
```sh
cd backend
cp .env.example .env  # Creates .env from a template (if available)
```
Then, open `.env` and replace the placeholders with your actual API keys:  
- **OpenAI API Key**: Required for transcript processing
- Azure computer Vision API Key & Endpoint: Optional for transcript processing

3️⃣ **Run the setup script**:  

🖥 On macOS/Linux Terminal:
```sh
./setup.sh
```
🖥 On Windows Command Prompt:
```sh
setup.bat
```
Alternatively, if you use Git Bash or WSL:
```sh
bash setup.sh
```

📌 **This will**:
- Set up a **Python virtual environment** and install required backend packages
- Install **Node.js dependencies** for the frontend
- Start both **backend** and **frontend** servers

4️⃣ **Access the web app**:  

Open http://localhost:3000 in your browser

---

## Manual Setup (If Scripts Fail)

### Backend Setup (FastAPI)
If the setup script fails, manually set up the backend:
```sh
cd backend
python -m venv venv  # Create a virtual environment
source venv/bin/activate  # Activate virtual environment (macOS/Linux)
venv\Scripts\activate  # Activate virtual environment (Windows)

pip install -r requirements.txt  # Install dependencies
uvicorn main:app --reload  # Start FastAPI server
```
📌 **Backend runs on**: http://localhost:8000

### Frontend Setup (React)
If the setup script fails, manually set up the frontend:
```sh
cd frontend
npx create-react-app my-app  # Install React app
cd my-app
npm install  # Install dependencies
npm start  # Start frontend
```
📌 **Frontend runs on**: http://localhost:3000

---

## Shutdown Instructions

To **properly stop** the backend, frontend, and virtual environment, run:  

🖥 On macOS/Linux Terminal:
```sh
./shutdown.sh
```
🖥 On Windows Command Prompt:
```sh
shutdown.bat
```
Alternatively, if you use Git Bash or WSL:
```sh
bash shutdown.sh
```

📌 **This will**:
- Stop **FastAPI backend**
- Stop **Vite frontend**
- Deactivate **Python virtual environment**

---

## Additional Notes

- **Backend runs on**: http://localhost:8000
- **Frontend runs on**: http://localhost:3000
- If you **encounter permission issues**:
    🖥 On macOS/Linux Terminal:
    ```sh
    chmod +x setup.sh shutdown.sh
    ```
    🖥 On Windows Command Prompt:
    ```sh
    chmod +x setup.bat shutdown.bat
    ```
    to make the scripts executable.
- If you need to **reinstall dependencies**, delete the venv/ directory and node_modules/, then rerun setup.sh or setup.bat.

---

## Contributing

Feel free to submit pull requests, issues, or feature suggestions!

📧 **Contact**: s.tehrani@westcliff.edu

