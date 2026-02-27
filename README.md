# PRIVEX — AI Privacy Firewall

> **Local-first, LLM-powered redaction of faces, text PII, and sensitive audio — with human-in-the-loop review before anything is permanently changed.**

---

## What is this?

PRIVEX is an AI privacy firewall that automatically detects and redacts sensitive personal information from images, audio, and text. It runs entirely on your machine — no data leaves your device.

The key idea: AI isn't perfect, so PRIVEX never blindly redacts. It proposes what to redact, explains *why* each item is sensitive, and lets you approve or dismiss each decision before the final file is exported.

---

## The Problem It Solves

Every day, people share images of ID cards, documents, screenshots, and audio recordings without realizing they contain sensitive data — Aadhaar numbers, bank details, phone numbers, faces. Manual redaction is tedious and error-prone. Existing tools either over-redact (destroying useful content) or under-redact (missing context-dependent PII).

**PRIVEX solves this with three principles:**

### 1. Contextual Intelligence
The system doesn't just pattern-match numbers — it understands context. A 16-digit number near "Visa" or "card" is a credit card and gets flagged. The same 16-digit number near "tracking" or "shipment" is a package ID and is left alone. The LLM reasons about *why* something is sensitive, not just *that* it matches a pattern.

### 2. Automated Redaction
Detected sensitive regions are automatically blacked out in the output — faces, text boxes, and audio segments — while the rest of the media stays intact and readable.

### 3. Human-in-the-Loop Review
Before anything is permanently changed, the user sees every proposed redaction with the AI's reasoning. Each item can be toggled on or off. Only after the user clicks **Apply** does the redaction get burned into the file.

---

## How It Works

```
Upload → Detect (Face + OCR + Whisper) → LLM Contextual Reasoning
       → Human Review UI → User Approves/Dismisses → Apply & Export
```

### Image Pipeline
1. **OpenCV DNN** detects faces (ResNet SSD, confidence > 0.7)
2. **PaddleOCR** extracts all text from the image
3. **Ollama (LLaMA 3)** receives each detected value + surrounding context and classifies it as sensitive or safe with a plain-English reason
4. Proposals are shown as overlay boxes on the original image — the user toggles each one
5. On approval, only the confirmed boxes are blacked out and the file is exported

### Audio Pipeline
1. **Whisper** transcribes audio with word-level timestamps
2. LLM + regex identifies sensitive values in the transcript
3. **ffmpeg** mutes only the exact time segments containing sensitive speech (30ms padding)

### Text Pipeline
1. Regex finds candidate values (numbers, dates, IDs)
2. LLM classifies each with context
3. Sensitive values are replaced with `█` blocks in the output

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | Python 3.10+, FastAPI, Uvicorn |
| Face Detection | OpenCV DNN (ResNet SSD) |
| OCR | PaddleOCR (PP-OCRv4) |
| Speech-to-Text | OpenAI Whisper (local, base model) |
| LLM | Ollama + LLaMA 3 (runs locally, offline) |
| Audio Muting | ffmpeg |
| Frontend | React 18, Vite |
| Styling | CSS Modules, IBM Plex Mono / Syne |

Everything runs locally. No cloud APIs required.

---

## Features

- **Drag-and-drop upload** for images, audio, and text
- **Animated pipeline visualizer** showing each processing stage
- **Interactive review board** — image overlay with toggleable redaction boxes
- **LLM reasoning shown per item** — e.g. "16-digit number near 'Visa' → credit card"
- **Filter view** — see only sensitive / only safe / all proposals
- **One-click approve all or dismiss all**
- **Download redacted file** after review
- **Live log terminal** showing backend processing in real time
- **Backend health indicator** in the header
- **Offline capable** — works without internet if Ollama is running

---

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- [Ollama](https://ollama.com) with `llama3` pulled
- ffmpeg (for audio redaction)
- OpenCV face model files in `backend/models/`

### Face Model Files

Download and place both files in `backend/models/`:
- [`deploy.prototxt`](https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt)
- [`res10_300x300_ssd_iter_140000.caffemodel`](https://github.com/opencv/opencv_3rdparty/raw/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel)

### Install & Run

```bash
# 1. Start Ollama in its own terminal
ollama pull llama3
ollama serve

# 2. Backend
cd backend
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**  
API docs at **http://localhost:8000/docs**

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | System status check |
| `POST` | `/review/propose` | Upload image → proposals + base64 preview (no redaction yet) |
| `POST` | `/review/apply` | Submit approved boxes → redacted file |
| `POST` | `/scan/audio` | Upload audio → Whisper + LLM redaction |
| `POST` | `/scan/text` | Submit plain text → PII detection + redacted output |
| `GET` | `/download/{filename}` | Download a redacted output file |

---

## Project Structure

```
privex/
├── backend/
│   ├── main.py                  ← FastAPI routes
│   ├── requirements.txt
│   ├── models/                  ← OpenCV face detection weights (add manually)
│   ├── outputs/                 ← redacted files saved here
│   └── services/
│       ├── llm_service.py       ← contextual LLM classification + regex fallback
│       ├── image_service.py     ← face detection, OCR, propose/apply two-phase pipeline
│       ├── audio_service.py     ← Whisper transcription + ffmpeg segment muting
│       └── text_service.py      ← text-only PII scan wrapper
│
└── frontend/
    └── src/
        ├── App.jsx              ← root, manages propose→review→apply flow
        ├── api/client.js        ← all API calls
        ├── hooks/useScan.js     ← scan state machine (audio/text)
        └── components/
            ├── ReviewBoard.jsx  ← human-in-the-loop review UI (image mode)
            ├── UploadPanel.jsx  ← drag-drop upload, mode tabs
            ├── Pipeline.jsx     ← animated stage indicator
            ├── ResultsPanel.jsx ← audio/text results display
            └── LogTerminal.jsx  ← live backend log stream
```

---

## Built for

This project was built as a hackathon prototype demonstrating that production-grade AI privacy tooling can run entirely locally — no cloud dependency, no data leaving the device — with a human always in control of the final output.

## Project Structure

```
privex/
├── start.sh                    ← run this to start everything
│
├── backend/
│   ├── main.py                 ← FastAPI app (endpoints)
│   ├── requirements.txt
│   ├── models/                 ← place your .caffemodel + .prototxt here
│   ├── outputs/                ← redacted files saved here
│   └── services/
│       ├── llm_service.py      ← your classify_text() + regex fallback
│       ├── image_service.py    ← your redact_image() → returns JSON
│       ├── audio_service.py    ← your redact_audio() → returns JSON
│       └── text_service.py     ← text-only scan wrapper
│
└── frontend/
    ├── package.json
    ├── vite.config.js          ← proxies /scan/* to localhost:8000
    └── src/
        ├── App.jsx
        ├── api/client.js       ← all fetch calls
        ├── hooks/useScan.js    ← scan state machine
        └── components/
            ├── Header.jsx      ← backend health check indicator
            ├── Pipeline.jsx    ← animated upload→detect→classify→redact→done
            ├── UploadPanel.jsx ← image/audio/text upload with drag-drop
            ├── ResultsPanel.jsx← detections list, redacted preview, download
            └── LogTerminal.jsx ← live log output
```

## Prerequisites

```bash
# 1. Ollama (local LLM)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3
ollama serve          # runs on localhost:11434

# 2. ffmpeg (for audio muting)
sudo apt install ffmpeg        # Ubuntu/Debian
brew install ffmpeg            # macOS

# 3. Face detection model files
# Download and place in backend/models/:
#   - res10_300x300_ssd_iter_140000.caffemodel
#   - deploy.prototxt
# Get from: https://github.com/opencv/opencv/tree/master/samples/dnn/face_detector

# 4. Node.js 18+ (for React frontend)
node --version
```

## Quick Start

```bash
chmod +x start.sh
./start.sh
```

Then open: **http://localhost:5173**

## Manual Start

```bash
# Terminal 1 — Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm install
npm run dev
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Backend status |
| POST | `/scan/image` | Upload image → face + OCR redaction |
| POST | `/scan/audio` | Upload audio → Whisper + LLM muting |
| POST | `/scan/text` | JSON body `{text}` → PII detection |
| GET | `/download/{filename}` | Download redacted output file |

Swagger UI: **http://localhost:8000/docs**

## What changed from test_script.py

- **Zero logic changes** — your exact detection algorithms are preserved
- Face detection, OCR matching, numeric/phrase audio matching: identical
- LLM prompt: identical
- Added: lazy model loading (load once, not per request)
- Added: structured JSON responses instead of print statements
- Added: unique filenames per request (no collisions)
- Added: FastAPI routes wrapping each function
