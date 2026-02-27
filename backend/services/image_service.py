"""
Image redaction service.
Your exact face detection + OCR + LLM logic, wrapped to return structured data.
"""

import cv2, numpy as np, os
from paddleocr import PaddleOCR
from services.llm_service import get_all_sensitive_values

_BASE        = os.path.dirname(os.path.dirname(__file__))
FACE_MODEL   = os.path.join(_BASE, "models", "res10_300x300_ssd_iter_140000.caffemodel")
FACE_CONFIG  = os.path.join(_BASE, "models", "deploy.prototxt")

# Lazy singletons — load once per process, not per request
_face_net = None
_ocr      = None

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


# ── Your exact face detection ──────────────────────────────────────────────────

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
        if conf > 0.5:
            box = dets[0, 0, i, 3:7] * np.array([w, h, w, h])
            sx, sy, ex, ey = box.astype("int")
            sx, sy = max(0, sx), max(0, sy)
            ex, ey = min(w, ex), min(h, ey)
            faces.append((int(sx), int(sy), int(ex - sx), int(ey - sy), round(conf, 3)))
    return faces


# ── Your exact image redact logic, returning structured data ───────────────────

def redact_image_file(input_path: str, output_path: str) -> dict:
    image = cv2.imread(input_path)
    if image is None:
        raise ValueError(f"Cannot read image: {input_path}")

    detections = []

    # 1. Face detection (your exact logic)
    faces = detect_faces(image)
    print(f"[FACE] {len(faces)} detected")
    for (x, y, w, h, conf) in faces:
        image[y:y+h, x:x+w] = (0, 0, 0)
        detections.append({
            "type": "face", "label": "Human Face",
            "confidence": conf,
            "bbox": {"x": x, "y": y, "w": w, "h": h},
            "source": "opencv-dnn",
        })

    # 2. OCR (your exact logic)
    ocr_result = _paddle().ocr(input_path)
    sensitive_values, entities, is_sensitive = [], [], False
    ocr_text = ""

    if ocr_result and ocr_result != [None]:
        lines    = [line[1][0] for block in ocr_result if block for line in block]
        ocr_text = " ".join(lines)
        print(f"[OCR] {len(lines)} lines")

        sensitive_values, entities, is_sensitive = get_all_sensitive_values(ocr_text)
        print(f"[PII] {len(sensitive_values)} sensitive values")

        # 3. Redact matched text boxes (your exact logic)
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
        "sensitive":    len(detections) > 0,
        "entity_count": len(detections),
        "detections":   detections,
        "ocr_text":     ocr_text,
        "face_count":   len(faces),
        "text_redacted": len([d for d in detections if d["type"] == "text"]),
    }
