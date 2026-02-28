"""
Image service — two-phase pipeline:

  Phase 1: propose_redactions()
    → Detects faces + OCR text
    → Sends each candidate to LLM WITH context for contextual reasoning
    → Returns proposed boxes + LLM reasoning to frontend
    → Does NOT modify image yet
    → Saves original image to disk keyed by session token

  Phase 2: apply_redactions()
    → Receives user-approved box list from frontend (after human review)
    → Loads original saved image
    → Burns in only approved redactions
    → Returns final redacted file for download
"""

import cv2, numpy as np, os, base64, re
from paddleocr import PaddleOCR
from services.llm_service import get_all_sensitive_values, propose_entities

_BASE       = os.path.dirname(os.path.dirname(__file__))
FACE_MODEL  = os.path.join(_BASE, "models", "res10_300x300_ssd_iter_140000.caffemodel")
FACE_CONFIG = os.path.join(_BASE, "models", "deploy.prototxt")
OUTPUT_DIR  = os.path.join(_BASE, "outputs")

_face_net = None
_ocr      = None


def _find_bbox(entity_text: str, ocr_bbox_map: dict) -> dict:
    """
    Multi-strategy bbox finder. Handles cases where LLM reconstructs
    multi-word entities that span multiple OCR boxes.

    Strategy 1: exact substring match in a single OCR line
    Strategy 2: case-insensitive / whitespace-normalised match
    Strategy 3: all tokens of entity_text found in the same OCR line
    Strategy 4: merge bboxes of all OCR lines whose text appears in entity_text
    Strategy 5: fall back to first OCR line that shares any token
    """
    if not ocr_bbox_map:
        return {"x": 0, "y": 0, "w": 0, "h": 0}

    norm_entity = re.sub(r'\s+', ' ', entity_text.strip()).upper()

    # Strategy 1 & 2: single-line exact / normalised match
    for ocr_line, bbox in ocr_bbox_map.items():
        norm_line = re.sub(r'\s+', ' ', ocr_line.strip()).upper()
        if norm_entity in norm_line or norm_line in norm_entity:
            return bbox

    # Strategy 3: all tokens present in one OCR line
    tokens = [t for t in norm_entity.split() if len(t) > 1]
    if tokens:
        for ocr_line, bbox in ocr_bbox_map.items():
            norm_line = re.sub(r'\s+', ' ', ocr_line.strip()).upper()
            if all(t in norm_line for t in tokens):
                return bbox

    # Strategy 4: merge bboxes of OCR lines whose text is contained in entity_text
    # (handles "MOTORIST HD MORGAN" where OCR has "MOTORIST", "HD", "MORGAN" separately)
    matching_bboxes = []
    for ocr_line, bbox in ocr_bbox_map.items():
        norm_line = re.sub(r'\s+', '', ocr_line.strip()).upper()
        norm_no_space = re.sub(r'\s+', '', norm_entity)
        # Check if this ocr line's content appears in the entity (as substring, no spaces)
        if norm_line and len(norm_line) > 1 and norm_line in norm_no_space:
            matching_bboxes.append(bbox)

    if matching_bboxes:
        # Merge all matching boxes into one enclosing bbox
        x1 = min(b["x"] for b in matching_bboxes)
        y1 = min(b["y"] for b in matching_bboxes)
        x2 = max(b["x"] + b["w"] for b in matching_bboxes)
        y2 = max(b["y"] + b["h"] for b in matching_bboxes)
        return {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1}

    # Strategy 5: any shared token (last resort)
    for token in tokens:
        if len(token) < 3: continue
        for ocr_line, bbox in ocr_bbox_map.items():
            if token in ocr_line.upper():
                return bbox

    print(f"[BBOX] No match for '{entity_text}' — will redact as zero-bbox (entity list only)")
    return {"x": 0, "y": 0, "w": 0, "h": 0}

def _net():
    global _face_net
    if _face_net is None:
        print("[INIT] Loading DNN face detector...")
        _face_net = cv2.dnn.readNetFromCaffe(FACE_CONFIG, FACE_MODEL)
    return _face_net

def _paddle():
    global _ocr
    if _ocr is None:
        print("[INIT] Loading PaddleOCR...")
        _ocr = PaddleOCR(use_angle_cls=True, lang="en")
    return _ocr


# ── Face detection ─────────────────────────────────────────────────────────────

def detect_faces(image: np.ndarray) -> list:
    h, w = image.shape[:2]
    blob = cv2.dnn.blobFromImage(
        cv2.resize(image, (300, 300)), 1.0, (300, 300), (104.0, 177.0, 123.0)
    )
    _net().setInput(blob)
    dets = _net().forward()
    faces = []
    for i in range(dets.shape[2]):
        conf = float(dets[0, 0, i, 2])
        if conf > 0.7:   # raised from 0.5 to reduce false positives
            box = dets[0, 0, i, 3:7] * np.array([w, h, w, h])
            sx, sy, ex, ey = box.astype("int")
            sx, sy = max(0, int(sx)), max(0, int(sy))
            ex, ey = min(w, int(ex)), min(h, int(ey))
            faces.append((sx, sy, ex - sx, ey - sy, round(conf, 3)))
    return faces


def _image_to_base64(image: np.ndarray) -> str:
    """Encode cv2 image to base64 JPEG for frontend preview."""
    _, buf = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf).decode("utf-8")


# ── PHASE 1: Propose redactions (no image modification) ───────────────────────

def propose_redactions(input_path: str, session_token: str) -> dict:
    """
    Detects faces + OCR candidates, sends to contextual LLM, returns proposals.
    The original image is kept at input_path (caller must not delete it).
    """
    image = cv2.imread(input_path)
    if image is None:
        raise ValueError(f"Cannot read image: {input_path}")

    h, w = image.shape[:2]
    proposals = []

    # ── 1. Face detection ──────────────────────────────────────────────────────
    faces = detect_faces(image)
    print(f"[FACE] {len(faces)} detected (threshold 0.7)")
    for (x, y, fw, fh, conf) in faces:
        proposals.append({
            "id":        f"face_{x}_{y}",
            "type":      "face",
            "label":     "Human Face",
            "reason":    "Face detected by OpenCV DNN — always sensitive",
            "sensitive": True,   # faces are always proposed as sensitive
            "confidence": conf,
            "approved":  True,   # pre-approved, user can toggle off
            "bbox":      {"x": x, "y": y, "w": fw, "h": fh},
            "source":    "opencv-dnn",
        })

    # ── 2. OCR + contextual LLM ────────────────────────────────────────────────
    ocr_result = _paddle().ocr(input_path)
    ocr_text   = ""
    # Map from text value → bbox for later lookup
    ocr_bbox_map: dict[str, dict] = {}

    if ocr_result and ocr_result != [None]:
        lines = [line[1][0] for block in ocr_result if block for line in block]
        ocr_text = " ".join(lines)
        print(f"[OCR] {len(lines)} lines: {ocr_text[:120]}...")

        # Build bbox map for all OCR lines
        for block in ocr_result:
            if not block: continue
            for line in block:
                box, (text, _) = line[0], line[1]
                xm = int(min(p[0] for p in box)); xM = int(max(p[0] for p in box))
                ym = int(min(p[1] for p in box)); yM = int(max(p[1] for p in box))
                ocr_bbox_map[text] = {"x": xm, "y": ym, "w": xM - xm, "h": yM - ym}

        # Get contextual LLM proposals for all candidates
        entities = propose_entities(ocr_text)
        print(f"[LLM] {len(entities)} candidates evaluated")

        for ent in entities:
            val = ent["text"]
            matched_bbox = _find_bbox(val, ocr_bbox_map)
            print(f"[BBOX] '{val[:40]}' → {matched_bbox}")

            proposals.append({
                "id":        f"text_{val[:20].replace(' ','_')}",
                "type":      "text",
                "label":     ent.get("label", "Text PII"),
                "value":     val,
                "context":   ent.get("context", ""),
                "reason":    ent.get("reason", ""),
                "sensitive": ent.get("sensitive", True),
                "confidence": 0.9 if ent.get("sensitive") else 0.3,
                "approved":  ent.get("sensitive", True),
                "bbox":      matched_bbox,
                "source":    "paddleocr+llm",
            })

    # ── 3. Return preview image (original, no redactions yet) ─────────────────
    preview_b64 = _image_to_base64(image)

    return {
        "session_token": session_token,
        "image_w":       w,
        "image_h":       h,
        "proposals":     proposals,
        "ocr_text":      ocr_text,
        "preview_b64":   preview_b64,   # original image for frontend overlay
        "sensitive_count": sum(1 for p in proposals if p["sensitive"]),
        "safe_count":      sum(1 for p in proposals if not p["sensitive"]),
    }


# ── PHASE 2: Apply approved redactions ────────────────────────────────────────

def apply_redactions(input_path: str, output_path: str, approved_boxes: list[dict]) -> dict:
    """
    approved_boxes: list of {"x", "y", "w", "h"} — only these get redacted.
    Loads original image, burns in redactions, saves output.
    Returns base64 of redacted image + output filename.
    """
    image = cv2.imread(input_path)
    if image is None:
        raise ValueError(f"Cannot read original image: {input_path}")

    applied = 0
    for box in approved_boxes:
        x, y, w, h = int(box["x"]), int(box["y"]), int(box["w"]), int(box["h"])
        if w > 0 and h > 0:
            # Black fill redaction
            image[y:y+h, x:x+w] = (0, 0, 0)
            applied += 1

    cv2.imwrite(output_path, image)
    redacted_b64 = _image_to_base64(image)

    return {
        "applied_count":  applied,
        "redacted_b64":   redacted_b64,
        "output_path":    output_path,
    }


# ── Legacy single-shot redact (kept for /scan/image backward compat) ──────────

def redact_image_file(input_path: str, output_path: str) -> dict:
    image = cv2.imread(input_path)
    if image is None:
        raise ValueError(f"Cannot read image: {input_path}")

    detections = []
    faces = detect_faces(image)
    for (x, y, w, h, conf) in faces:
        image[y:y+h, x:x+w] = (0, 0, 0)
        detections.append({
            "type": "face", "label": "Human Face", "confidence": conf,
            "bbox": {"x": x, "y": y, "w": w, "h": h}, "source": "opencv-dnn",
        })

    ocr_result = _paddle().ocr(input_path)
    ocr_text = ""
    if ocr_result and ocr_result != [None]:
        lines    = [line[1][0] for block in ocr_result if block for line in block]
        ocr_text = " ".join(lines)
        sensitive_values, entities, _ = get_all_sensitive_values(ocr_text)
        for block in ocr_result:
            if not block: continue
            for line in block:
                box, (text, conf) = line[0], line[1]
                if any(val and val in text for val in sensitive_values):
                    xm = int(min(p[0] for p in box)); xM = int(max(p[0] for p in box))
                    ym = int(min(p[1] for p in box)); yM = int(max(p[1] for p in box))
                    image[ym:yM, xm:xM] = (0, 0, 0)
                    detections.append({
                        "type": "text", "label": "Sensitive Text",
                        "value": text, "confidence": round(float(conf), 3),
                        "bbox": {"x": xm, "y": ym, "w": xM-xm, "h": yM-ym},
                        "source": "paddleocr+llm",
                    })

    cv2.imwrite(output_path, image)
    return {
        "sensitive": len(detections) > 0,
        "entity_count": len(detections),
        "detections": detections,
        "ocr_text": ocr_text,
        "face_count": len(faces),
        "text_redacted": len([d for d in detections if d["type"] == "text"]),
    }