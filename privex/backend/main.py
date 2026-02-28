"""
PRIVEX — Privacy Firewall API
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn, os, shutil, uuid

from services.image_service import redact_image_file, propose_redactions, apply_redactions
from services.audio_service import redact_audio_file
from services.text_service  import classify_text_only
from services.video_service import redact_video_file
import services.llm_service as llm_svc

_sessions: dict = {}

app = FastAPI(title="PRIVEX Privacy Firewall", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    engine = "gemini" if llm_svc.GEMINI_API_KEY else "ollama"
    return {"status": "ok", "engine": engine}


# ── LLM config (switch Ollama ↔ Gemini at runtime) ────────────────────────────

class LLMConfig(BaseModel):
    gemini_api_key: str = ""

@app.post("/config/llm")
async def set_llm_config(body: LLMConfig):
    llm_svc.GEMINI_API_KEY = body.gemini_api_key.strip()
    engine = "gemini" if llm_svc.GEMINI_API_KEY else "ollama"
    print(f"[CONFIG] LLM engine → {engine}")
    return {"engine": engine, "status": "ok"}

@app.get("/config/llm")
async def get_llm_config():
    engine = "gemini" if llm_svc.GEMINI_API_KEY else "ollama"
    return {"engine": engine, "gemini_configured": bool(llm_svc.GEMINI_API_KEY)}


# ── Image (legacy single-shot) ─────────────────────────────────────────────────

@app.post("/scan/image")
async def scan_image(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "Must be an image file")
    ext   = os.path.splitext(file.filename or "upload.jpg")[1] or ".jpg"
    token = uuid.uuid4().hex
    inp   = os.path.join(OUTPUT_DIR, f"in_{token}{ext}")
    out   = os.path.join(OUTPUT_DIR, f"redacted_{token}{ext}")
    with open(inp, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        result = redact_image_file(inp, out)
        result["redacted_file"] = f"redacted_{token}{ext}"
        return result
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        if os.path.exists(inp): os.remove(inp)


# ── Audio ──────────────────────────────────────────────────────────────────────

@app.post("/scan/audio")
async def scan_audio(file: UploadFile = File(...)):
    ext   = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    token = uuid.uuid4().hex
    inp   = os.path.join(OUTPUT_DIR, f"in_{token}{ext}")
    out   = os.path.join(OUTPUT_DIR, f"redacted_{token}{ext}")
    with open(inp, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        result = redact_audio_file(inp, out)
        result["redacted_file"] = f"redacted_{token}{ext}"
        return result
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        if os.path.exists(inp): os.remove(inp)


# ── Video ──────────────────────────────────────────────────────────────────────

@app.post("/scan/video")
async def scan_video(file: UploadFile = File(...)):
    """
    Upload a short video clip (2–3 seconds).
    Runs face detection + OCR on frames + Whisper on audio.
    Returns redacted .mp4.
    """
    ext   = os.path.splitext(file.filename or "video.mp4")[1] or ".mp4"
    token = uuid.uuid4().hex
    inp   = os.path.join(OUTPUT_DIR, f"in_{token}{ext}")
    out   = os.path.join(OUTPUT_DIR, f"redacted_{token}.mp4")
    with open(inp, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        result = redact_video_file(inp, out)
        result["redacted_file"] = f"redacted_{token}.mp4"
        return result
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        if os.path.exists(inp): os.remove(inp)


# ── Text ───────────────────────────────────────────────────────────────────────

class TextIn(BaseModel):
    text: str

@app.post("/scan/text")
async def scan_text(body: TextIn):
    try:
        return classify_text_only(body.text)
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Review Phase 1: propose ───────────────────────────────────────────────────

@app.post("/review/propose")
async def review_propose(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(400, "Must be an image file")
    ext   = os.path.splitext(file.filename or "upload.jpg")[1] or ".jpg"
    token = uuid.uuid4().hex
    inp   = os.path.join(OUTPUT_DIR, f"orig_{token}{ext}")
    with open(inp, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        result = propose_redactions(inp, token)
        _sessions[token] = inp
        return result
    except Exception as e:
        if os.path.exists(inp): os.remove(inp)
        raise HTTPException(500, str(e))


# ── Review Phase 2: apply ─────────────────────────────────────────────────────

class BBox(BaseModel):
    x: int
    y: int
    w: int
    h: int

class ApplyRequest(BaseModel):
    session_token: str
    approved_boxes: list[BBox]

@app.post("/review/apply")
async def review_apply(body: ApplyRequest):
    inp = _sessions.get(body.session_token)
    if not inp or not os.path.exists(inp):
        raise HTTPException(404, "Session not found or expired. Re-upload the image.")
    ext = os.path.splitext(inp)[1]
    out = os.path.join(OUTPUT_DIR, f"redacted_{body.session_token}{ext}")
    try:
        from services.image_service import apply_redactions
        boxes  = [b.model_dump() for b in body.approved_boxes]
        result = apply_redactions(inp, out, boxes)
        result["redacted_file"] = os.path.basename(out)
        os.remove(inp)
        del _sessions[body.session_token]
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


# ── Download ───────────────────────────────────────────────────────────────────

@app.get("/download/{filename}")
async def download(filename: str):
    safe = os.path.basename(filename)
    path = os.path.join(OUTPUT_DIR, safe)
    if not os.path.exists(path):
        raise HTTPException(404, "File not found")
    return FileResponse(path, filename=safe)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
