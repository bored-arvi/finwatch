"""
PRIVEX — Privacy Firewall API
Wraps your working test_script.py into a clean FastAPI backend.
"""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn, os, shutil, uuid

from services.image_service import redact_image_file
from services.audio_service import redact_audio_file
from services.text_service  import classify_text_only

app = FastAPI(title="PRIVEX Privacy Firewall", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.get("/health")
def health():
    return {"status": "ok", "mode": "local-first"}


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


class TextIn(BaseModel):
    text: str

@app.post("/scan/text")
async def scan_text(body: TextIn):
    try:
        return classify_text_only(body.text)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/download/{filename}")
async def download(filename: str):
    safe = os.path.basename(filename)
    path = os.path.join(OUTPUT_DIR, safe)
    if not os.path.exists(path):
        raise HTTPException(404, "File not found")
    return FileResponse(path, filename=safe)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
