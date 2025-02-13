# WU Transcript Manager

## 🌐 Overview
This project is a **full-stack web application** for managing and categorizing transcripts. It consists of:
- **Backend**: FastAPI (Python) with SQLite database
- **Frontend**: React (Pure React)
- **Machine Learning**: SBERT & OpenAI API for text processing
- **OCR**: OpenCV & Tesseract for text extraction from PDFs

---

## 🚀 Setup Instructions

### 🔧 **Prerequisites**
Ensure your system meets the following requirements:
- **Python 3.9+**
- **Node.js (v20+)**
- **npm** (comes with Node.js)
- **virtualenv** (for Python firtual environment)
- **Tesseract OCR 5.3+** (for PDF test extraction)

If missing, the setup script will attempt to install them automatically.

### 📥 **Clone the Repository**
```sh
git clone https://github.com/mxw271/wu-transcript-manager.git
cd wu-transcript-manager
```

### 🔑 **Update Your API Keys**

**Navigate to the backend `.env` file** (located in `backend/.env`).

Replace the placeholders with your **actual API keys**:  

```sh
OPENAI_API_KEY=your-openai-api-key
AZURE_CV_API_KEY=your-azure-computer-vision-api-key
AZURE_CV_ENDPOINT=your-azure-computer-vision-endpoint
```
- **OpenAI API Key**: Required for transcript processing.
- Azure Computer Vision API Key & Endpoint: Optional for transcript processing.

If you update your API keys after starting the servers, run the shutdown script and rerun the start script.

### 🛠️ **Initial Setup (Run Once)**:  
Run **this step only once** to install dependencies.

🖥 On macOS/Linux Terminal:
```sh
./setup.sh
```
🖥 On Windows Command Prompt:
```bat
setup.bat
```
Alternatively, if you use Git Bash or WSL:
```sh
bash setup.sh
```

**📌 This will**:
- Set up a **Python virtual environment** and install required backend dependencies.
- Install **Node.js dependencies** for the frontend.
- Install **OCR dependencies**.
- **Will not start the servers** (you must run the start script separately)

---

## 🚀 Start the App (Run Every Time)

Ater setup, **use this command every time you want to run the app**.

🖥 On macOS/Linux Terminal:
```sh
./start.sh
```
🖥 On Windows Command Prompt:
```bat
start.bat
```
Alternatively, if you use Git Bash or WSL:
```sh
bash start.sh
```

**📌 This will**:
- Activate the **Python virtual environment**.
- Start the **FastAPI backend** (http://localhost:8000).
- Start the **React frontend** (http://localhost:3000).
- Keeps the terminal open to prevent accidental closure.

---

## 🛑 Shutdown the App

To **properly stop the servers**, run:  

🖥 On macOS/Linux Terminal:
```sh
./shutdown.sh
```
🖥 On Windows Command Prompt:
```bat
shutdown.bat
```
Alternatively, if you use Git Bash or WSL:
```sh
bash shutdown.sh
```

**📌 This will**:
- Stop **React frontend**
- Stop **FastAPI backend**
- Deactivate **Python virtual environment**

---

## 💡 Additional Notes

- If you **encounter permission issues**:
    🖥 On macOS/Linux Terminal:
    ```sh
    chmod +x setup.sh start.sh shutdown.sh
    ```
    🖥 On Windows Command Prompt:
    ```bat
    icacls setup.bat /grant %USERNAME%:F
    icacls start.bat /grant %USERNAME%:F
    icacls shutdown.bat /grant %USERNAME%:F
    ```
    Alternatively, if you use Git Bash or WSL:
    ```sh
    chmod +x setup.sh start.sh shutdown.sh
    ```
    to make the scripts executable.
- If you need to **reinstall dependencies**, delete the `venv/` directory and `node_modules/`, then rerun the setup script.

---

## 🤝 Contributing

Feel free to submit pull requests, issues, or feature suggestions!

**📧 Contact**: s.tehrani@westcliff.edu

