# PRIVEX — AI Privacy Firewall

Your working `test_script.py` refactored into a clean FastAPI backend + React frontend.

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
