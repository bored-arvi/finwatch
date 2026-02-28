"""
Video redaction service — designed for short clips (2–3 seconds).

Pipeline:
  1. Read all frames with OpenCV
  2. OCR sampled at 1 frame/second (not every frame — too slow)
  3. LLM classifies all OCR text once for the whole clip
  4. Face detection on every frame
  5. Redact faces + sensitive text on every frame
  6. Write silent redacted video
  7. Extract original audio → Whisper → mute sensitive segments
  8. Merge redacted video + muted audio with ffmpeg → final .mp4
"""

import cv2, numpy as np, os, uuid, subprocess, shutil
from services.llm_service import get_all_sensitive_values
from services.image_service import detect_faces, _paddle, _image_to_base64
from services.audio_service import (
    merge_intervals, find_mute_ranges, classify_audio_transcript
)

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs")


def _ocr_frame(frame: np.ndarray, tmp_path: str):
    """Run PaddleOCR on one frame. Returns (text, bbox_map)."""
    cv2.imwrite(tmp_path, frame)
    result = _paddle().ocr(tmp_path)
    try: os.remove(tmp_path)
    except: pass

    if not result or result == [None]:
        return "", {}

    lines    = [line[1][0] for block in result if block for line in block]
    ocr_text = " ".join(lines)

    bbox_map = {}
    for block in result:
        if not block: continue
        for line in block:
            box, (line_text, _) = line[0], line[1]
            xm = int(min(p[0] for p in box)); xM = int(max(p[0] for p in box))
            ym = int(min(p[1] for p in box)); yM = int(max(p[1] for p in box))
            bbox_map[line_text] = {"x": xm, "y": ym, "w": xM - xm, "h": yM - ym}

    return ocr_text, bbox_map


def _redact_frame(frame, face_boxes, sensitive_values, bbox_map):
    """Black-fill faces and sensitive text boxes on a frame copy."""
    out = frame.copy()
    for (x, y, w, h, _) in face_boxes:
        out[y:y+h, x:x+w] = (0, 0, 0)
    for line_text, bbox in bbox_map.items():
        if any(val and val in line_text for val in sensitive_values):
            x, y, w, h = bbox["x"], bbox["y"], bbox["w"], bbox["h"]
            if w > 0 and h > 0:
                out[y:y+h, x:x+w] = (0, 0, 0)
    return out


def redact_video_file(input_path: str, output_path: str) -> dict:
    token      = uuid.uuid4().hex
    frames_dir = os.path.join(OUTPUT_DIR, f"frames_{token}")
    os.makedirs(frames_dir, exist_ok=True)

    tmp_video  = os.path.join(OUTPUT_DIR, f"tmp_vid_{token}.mp4")
    audio_path = os.path.join(OUTPUT_DIR, f"audio_{token}.wav")

    try:
        # ── 1. Read all frames ────────────────────────────────────────────────
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {input_path}")

        fps    = cap.get(cv2.CAP_PROP_FPS) or 24.0
        width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        total  = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        dur    = total / fps
        print(f"[VIDEO] {width}x{height} @ {fps:.1f}fps | {total} frames | {dur:.1f}s")

        frames = []
        while True:
            ret, frame = cap.read()
            if not ret: break
            frames.append(frame)
        cap.release()
        print(f"[VIDEO] Read {len(frames)} frames")

        # ── 2. OCR on 1 frame per second ─────────────────────────────────────
        sample_every = max(1, int(fps))
        all_ocr_text = ""
        bbox_maps    = {}

        for i, frame in enumerate(frames):
            if i % sample_every == 0:
                tmp = os.path.join(frames_dir, f"ocr_{i}.jpg")
                ocr_text, bmap = _ocr_frame(frame, tmp)
                bbox_maps[i] = bmap   # always store even if empty
                if ocr_text:
                    all_ocr_text += " " + ocr_text
                    print(f"[OCR] Frame {i}: {ocr_text[:80]}")
                else:
                    print(f"[OCR] Frame {i}: (no text detected)")

        # ── 3. LLM classifies OCR text once ──────────────────────────────────
        sensitive_values = []
        if all_ocr_text.strip():
            sv, _, _ = get_all_sensitive_values(all_ocr_text.strip())
            sensitive_values = sv
            print(f"[LLM] {len(sensitive_values)} sensitive: {sensitive_values}")

        # nearest-sample bbox lookup
        sampled_idxs = sorted(bbox_maps.keys())
        def bbox_for(idx):
            if not sampled_idxs: return {}
            return bbox_maps[min(sampled_idxs, key=lambda s: abs(s - idx))]

        # ── 4 & 5. Face-detect + redact every frame ───────────────────────────
        redacted = []
        total_faces = 0
        for i, frame in enumerate(frames):
            faces = detect_faces(frame)
            total_faces += len(faces)
            redacted.append(_redact_frame(frame, faces, sensitive_values, bbox_for(i)))
        print(f"[VIDEO] {total_faces} face detections across {len(frames)} frames")

        # ── 6. Write silent redacted video ────────────────────────────────────
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(tmp_video, fourcc, fps, (width, height))
        for f in redacted:
            writer.write(f)
        writer.release()
        print(f"[VIDEO] Silent redacted video written")

        # ── 7. Extract + mute audio ───────────────────────────────────────────
        muted_segments = []
        has_audio = False

        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=codec_type", "-of", "csv=p=0", input_path],
            capture_output=True, text=True
        )
        if "audio" in probe.stdout:
            subprocess.run(
                ["ffmpeg", "-y", "-i", input_path, "-vn",
                 "-acodec", "pcm_s16le", "-ar", "16000", audio_path],
                capture_output=True
            )
            has_audio = os.path.exists(audio_path) and os.path.getsize(audio_path) > 0
            print(f"[VIDEO] Audio extracted: {has_audio}")

        if has_audio:
            try:
                import whisper as _whisper
                wm = _whisper.load_model("base")
                wr = wm.transcribe(audio_path, language="en", word_timestamps=True,
                                   fp16=False, temperature=0, beam_size=5)
                transcript = wr["text"]
                print(f"[WHISPER] {transcript}")

                words = [
                    {"text": w["word"].strip(), "start": w["start"], "end": w["end"]}
                    for seg in wr["segments"] for w in seg.get("words", [])
                ]
                audio_sv = classify_audio_transcript(transcript)
                mutes    = find_mute_ranges(words, audio_sv)
                merged   = merge_intervals(mutes)
                muted_segments = merge_intervals(
                    [(max(0, s - 0.03), e + 0.03) for s, e in merged]
                )

                if muted_segments:
                    muted_audio = os.path.join(OUTPUT_DIR, f"muted_{token}.wav")
                    filters = ",".join(
                        f"volume=enable='between(t,{s},{e})':volume=0"
                        for s, e in muted_segments
                    )
                    subprocess.run(
                        ["ffmpeg", "-y", "-i", audio_path, "-af", filters, muted_audio],
                        capture_output=True, check=True
                    )
                    os.replace(muted_audio, audio_path)
                    print(f"[VIDEO] {len(muted_segments)} audio segments muted")
            except Exception as e:
                print(f"[VIDEO AUDIO ERROR] {e} — keeping original audio")

        # ── 8. Merge video + audio ────────────────────────────────────────────
        if has_audio:
            subprocess.run(
                ["ffmpeg", "-y", "-i", tmp_video, "-i", audio_path,
                 "-c:v", "libx264", "-c:a", "aac", "-shortest", output_path],
                capture_output=True, check=True
            )
        else:
            subprocess.run(
                ["ffmpeg", "-y", "-i", tmp_video, "-c:v", "libx264", output_path],
                capture_output=True, check=True
            )
        print(f"[VIDEO] Done → {output_path}")

        thumb = _image_to_base64(redacted[0]) if redacted else ""

        return {
            "sensitive":        len(sensitive_values) > 0 or total_faces > 0,
            # These field names match what ResultsPanel reads
            "face_count":       total_faces,         # → Faces stat
            "text_redacted":    len(sensitive_values), # → Text PII stat
            "muted_count":      len(muted_segments),  # → Audio Mutes stat
            "entity_count":     len(sensitive_values) + total_faces,
            # Entities list — shown in the detections list
            "entities": (
                [{"type": "face", "label": "Human Face",
                  "source": "opencv-dnn", "confidence": 0.9}
                 for _ in range(min(total_faces, 5))]  # cap at 5 to avoid flooding list
                +
                [{"type": "text", "label": e, "text": e,
                  "source": "llm+ocr", "confidence": 0.85}
                 for e in sensitive_values]
            ),
            # Extra video-specific fields
            "sensitive_values": sensitive_values,
            "face_detections":  total_faces,
            "frames_processed": len(frames),
            "duration_seconds": round(dur, 2),
            "ocr_text":         all_ocr_text.strip(),
            "muted_segments":   [{"start": s, "end": e} for s, e in muted_segments],
            "thumbnail_b64":    thumb,
        }

    finally:
        shutil.rmtree(frames_dir, ignore_errors=True)
        for f in [tmp_video, audio_path]:
            if os.path.exists(f): os.remove(f)