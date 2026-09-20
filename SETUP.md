# Nyaya Setup Guide

This file contains only the steps required to install and start the project on
macOS, Linux, or Windows.

## 1. Prerequisites

Install:

- Git
- Python 3.12
- either Conda or Python `venv`
- Node.js 22 or later
- npm 10 or later
- a Gemini API key
- a Pinecone API key and populated Pinecone index

## 2. Open the project

```bash
cd Indian-Legal-Rag
```

## 3. Create a Python environment

Choose one option.

### Conda on macOS, Linux, or Windows

```bash
conda create -n lega12 python=3.12
conda activate lega12
```

### Python `venv` on macOS or Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

If `python3` is unavailable but `python` points to Python 3.12:

```bash
python -m venv .venv
source .venv/bin/activate
```

### Python `venv` on Windows Command Prompt

```bat
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
```

### Python `venv` on Windows PowerShell

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 4. Install backend dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 5. Create `.env`

Create the local environment file from the template.

### macOS or Linux

```bash
cp .env.example .env
```

### Windows Command Prompt

```bat
copy .env.example .env
```

### Windows PowerShell

```powershell
Copy-Item .env.example .env
```

Open `.env` and enter the required configuration:

```dotenv
GEMINI_API_KEY=PASTE_YOUR_GEMINI_API_KEY_HERE
PINECONE_API_KEY=PASTE_YOUR_PINECONE_API_KEY_HERE
PINECONE_INDEX=indian-legal-rag
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
GEMINI_MODEL=gemini-3.6-flash
TOP_K=30
```

Use the exact name of your populated Pinecone index. Do not commit `.env`.

## 6. Install the frontend

```bash
cd frontend
npm ci
```

## 7. Development mode

Keep two terminals open.

### Terminal 1: FastAPI backend

Open the repository root, activate the Python environment created above, and
run:

```bash
python -m uvicorn src.app:app --reload
```

### Terminal 2: React frontend

```bash
cd Indian-Legal-Rag/frontend
npm run dev
```

Open `http://localhost:5173`.

## 8. Production-style local mode

Build the frontend:

```bash
cd frontend
npm run build
cd ..
```

Start FastAPI from the repository root:

```bash
python -m uvicorn src.app:app --reload
```

Open `http://127.0.0.1:8000`.

## 9. Speech-to-text

Use a supported browser such as Chrome. Select the spoken language in Settings,
press **Voice**, allow microphone permission, speak, and review the transcript
before sending it. Microphone access works on `localhost`; a deployed site must
use HTTPS. No additional speech package or API key is required.
