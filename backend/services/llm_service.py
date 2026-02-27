"""
LLM classification + regex fallback.
Your exact logic from test_script.py, extracted into a reusable service.
"""

import re, json, requests

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL      = "llama3"

SYSTEM_PROMPT = """
You are a privacy extraction engine.

Extract ALL sensitive personal information VALUES from the text.

Sensitive values include:
- Full personal names
- Employee IDs
- Bank account numbers
- Credit/debit card numbers
- CVV numbers
- Phone numbers
- Email addresses
- Government IDs (Aadhaar, PAN, passport, driving license, etc.)
- UPI IDs
- IFSC codes
- Dates of birth
- Addresses
- OTP codes
- Transaction numbers

IMPORTANT:
- Extract literal values only.
- Do NOT return labels.
- Return valid JSON only.
- No explanation.

{
  "sensitive": true/false,
  "entities": [{"text": "exact sensitive value"}]
}
"""

# ── Your exact LLM call ────────────────────────────────────────────────────────

def classify_text(text: str) -> dict:
    payload = {
        "model":   MODEL,
        "prompt":  SYSTEM_PROMPT + "\n\nText:\n" + text,
        "stream":  False,
        "format":  "json",
        "options": {"temperature": 0, "num_predict": 150}
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=180)
        raw = response.json().get("response", "").strip()
        print("[LLM RAW]", raw)
        return json.loads(raw)
    except Exception as e:
        print(f"[LLM ERROR] {e} — falling back to rule-based")
        return {"sensitive": False, "entities": []}


# ── Your exact regex fallback ──────────────────────────────────────────────────

def extract_numeric_entities(text: str) -> list:
    patterns = [
        r"\b\d{8,}\b",
        r"\b\d{2}/\d{2}/\d{4}\b",
        r"\b\d{10}\b",
        r"\b\d{12,16}\b",
    ]
    found = []
    for p in patterns:
        found.extend(re.findall(p, text))
    return list(set(found))


# ── Combined helper used by image + audio + text services ─────────────────────

def get_all_sensitive_values(text: str):
    """
    Returns (sensitive_values: list[str], entities: list[dict], is_sensitive: bool)
    """
    llm_result  = classify_text(text)
    llm_vals    = [e["text"] for e in llm_result.get("entities", []) if isinstance(e, dict) and e.get("text")]
    regex_vals  = extract_numeric_entities(text)

    combined = list(set(llm_vals + regex_vals))
    combined = [v.strip() for v in combined if v and v.strip()]

    entities = (
        [{"text": v, "source": "llm"}   for v in llm_vals] +
        [{"text": v, "source": "regex"} for v in regex_vals if v not in llm_vals]
    )
    return combined, entities, llm_result.get("sensitive", len(combined) > 0)


# ── Text-only scan (for /scan/text) ───────────────────────────────────────────

def classify_text_only(text: str) -> dict:
    sensitive_values, entities, is_sensitive = get_all_sensitive_values(text)

    redacted = text
    for val in sorted(sensitive_values, key=len, reverse=True):
        redacted = redacted.replace(val, "█" * len(val))

    return {
        "sensitive":      is_sensitive,
        "entity_count":   len(entities),
        "entities":       entities,
        "redacted_text":  redacted,
    }
