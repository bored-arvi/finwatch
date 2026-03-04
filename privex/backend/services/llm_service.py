"""
LLM service — Ollama (local) or Gemini (cloud).

Drop-in upgrade: set GEMINI_API_KEY env var OR call /config/llm at runtime
to switch engines. All prompts are identical regardless of engine.
"""

import re, json, requests, os

# ── Engine routing ─────────────────────────────────────────────────────────────

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"

# Can be set via env var at startup OR patched at runtime via /config/llm
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# gemini-2.5-flash uses v1beta endpoint
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-pro:generateContent"

def _use_gemini() -> bool:
    return bool(GEMINI_API_KEY)

def _call_llm(prompt: str, max_tokens: int = 800) -> str:
    """Single entry point. Routes to Gemini if key set, else Ollama."""
    if _use_gemini():
        print("[LLM] → Gemini")
        return _call_gemini(prompt, max_tokens)
    print("[LLM] → Ollama")
    return _call_ollama(prompt, max_tokens)

def _call_ollama(prompt: str, max_tokens: int) -> str:
    payload = {
        "model":   OLLAMA_MODEL,
        "prompt":  prompt,
        "stream":  False,
        "format":  "json",
        "options": {"temperature": 0, "num_predict": max_tokens}
    }
    r = requests.post(OLLAMA_URL, json=payload, timeout=180)
    return r.json().get("response", "").strip()

def _call_gemini(prompt: str, max_tokens: int) -> str:
    if not GEMINI_API_KEY or not GEMINI_API_KEY.strip():
        raise Exception("Gemini API key not set")

    headers = {"Content-Type": "application/json"}
    params  = {"key": GEMINI_API_KEY}

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": max_tokens
        }
    }

    r = requests.post(
        GEMINI_URL,
        headers=headers,
        params=params,
        json=payload,
        timeout=120
    )

    if not r.ok:
        print(f"[GEMINI ERROR] {r.status_code}")
        print(r.text)
        raise Exception(f"Gemini API error {r.status_code}")

    data = r.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise Exception("Gemini returned no candidates")

    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts:
        raise Exception("Gemini returned empty content")

    text = "".join(p.get("text", "") for p in parts).strip()

    return _clean_llm_json(text)


# ── Prompts (unchanged from your version) ─────────────────────────────────────

CONTEXTUAL_PROMPT = """You are a privacy extraction and classification engine.

You will receive a list of candidate values found in an image or document, each with surrounding context.

Extract ALL sensitive personal information VALUES and for EACH candidate, decide if it is truly sensitive personal information that must be redacted.

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

Use context clues to reason correctly:
- A 16-digit number near "card", "Visa", "Mastercard", "CVV", wallet → SENSITIVE (credit card)
- A 16-digit number near "tracking", "order", "shipment", "barcode", package → SAFE (tracking number)
- A name near "From:", "To:", personal letter, ID card → SENSITIVE
- A name near "Brand:", "Product:", company logo → SAFE
- A phone number in personal contact info → SENSITIVE
- A phone number that is a customer service hotline → SAFE
- An address that is someone's home → SENSITIVE
- An address that is a business/office → lean SAFE
- Aadhaar, PAN, passport, driving license numbers → always SENSITIVE
- Employee ID, bank account, UPI, IFSC, CVV, OTP → always SENSITIVE
- Date of birth in personal context → SENSITIVE
- Generic dates (invoice date, expiry date on product) → SAFE
- If the document contains words like LICENSE, DL, DLN, PASSPORT, AADHAAR, PAN, DOB, AAMVA, SSN → treat ALL numbers on that document as SENSITIVE by default
- Any number near "DL:", "DLN:", "ID:", "No.", "DUPS:", "DOB." on a card → always SENSITIVE
- Short repeated numbers like 99999999 or 000 on an ID card → SENSITIVE (sample license number)
- Any alphanumeric string on a card that has LICENSE or PASSPORT anywhere in the image → SENSITIVE

IMPORTANT:
- Extract literal values only
- Return valid JSON only, no explanation
IMPORTANT:
- The JSON must be complete and properly closed.
- Do not stop early.
- Ensure all brackets and quotes are closed.

{
  "results": [
    {
      "text": "exact value as given",
      "sensitive": true or false,
      "reason": "one short sentence explaining why",
      "label": "human readable type e.g. Credit Card, Tracking Number, Full Name"
    }
  ]
}
"""

FULL_TEXT_PROMPT = """You are a privacy extraction engine.

You are given the FULL OCR text of a document.

Extract ALL sensitive personal information exactly as written.

Sensitive information includes:
- Full names (including ALL CAPS names on ID cards)
- Home addresses
- Dates of birth
- Government ID numbers (DL, Passport, Aadhaar, PAN)
- Employee IDs
- Bank account numbers
- Credit/debit card numbers
- CVV
- Phone numbers
- Email addresses
- IFSC, UPI IDs
- OTP codes
- Transaction numbers

CRITICAL RULES:
- If the document contains words like LICENSE, DL, CDL, PASSPORT, AADHAAR, PAN → treat printed personal fields as sensitive.
- On ID cards, printed name and address are ALWAYS sensitive.
- Extract values exactly as they appear. Do not normalize spacing.
- Government IDs often start with letters followed by numbers e.g. "1D123456789", "D123456789" — always extract these.
- Extract the FULL name, not just the last name. If you see "MOTORIST HD MORGAN" extract all three words together as one entity.
- Do NOT split names into parts — return the complete name string as one entity.
- License/ID numbers may be prefixed with letters — extract the full alphanumeric string.

Return ONLY valid JSON:
{
  "entities": [
    {
      "text": "exact value",
      "label": "type"
    }
  ]
}

Document Text:
"""

AUDIO_PROMPT = """You are a privacy redaction engine for spoken audio transcripts.

Extract ALL sensitive personal information from the transcript below, exactly as the words appear in the text so they can be matched back to timestamps.

Sensitive information includes:
- Full names (e.g. "John Smith")
- Dates of birth — including spelled-out months (e.g. "January 7, 1973" or "the 7th of January 1973")
- Phone numbers — including spoken with dashes or spaces (e.g. "987-654-3210" or "nine eight seven six five four")
- Email addresses
- Bank account numbers, card numbers, CVV
- Government IDs (Aadhaar, PAN, passport, driving license)
- Home addresses
- OTP or PIN codes
- Any other personal identifying information

Return ONLY valid JSON, no explanation:
{
  "sensitive": true or false,
  "entities": [
    {
      "text": "exact phrase as it appears in the transcript",
      "label": "type e.g. Date of Birth, Phone Number, Full Name"
    }
  ]
}

Transcript:
"""


# ── LLM callers (now all route through _call_llm) ─────────────────────────────

def classify_audio_transcript(transcript: str) -> list:
    try:
        raw = _call_llm(AUDIO_PROMPT + transcript, max_tokens=500)
        print("[LLM AUDIO RAW]", raw)
        parsed = json.loads(raw)
        values = [e["text"] for e in parsed.get("entities", [])
                  if isinstance(e, dict) and e.get("text")]
        print(f"[LLM AUDIO] {len(values)} sensitive phrases: {values}")
        return values
    except Exception as e:
        print(f"[LLM AUDIO ERROR] {e}")
        return []

def classify_with_context(candidates: list) -> list:
    if not candidates:
        return []
    items = "\n".join(
        f'{i+1}. Value: "{c["text"]}" | Context: "{c["context"]}"'
        for i, c in enumerate(candidates)
    )
    try:
        raw = _call_llm(CONTEXTUAL_PROMPT + f"\n\nCandidates:\n{items}", max_tokens=1500)
        print("[LLM CONTEXTUAL RAW]", raw)
        raw = _clean_llm_json(raw)
        try:
            return json.loads(raw).get("results", [])
        except json.JSONDecodeError:
            print("⚠ Contextual JSON truncated, attempting recovery")

            # Try bracket balancing recovery
            start = raw.find("{")
            if start == -1:
                raise

            cleaned = raw[start:]

            # Balance brackets manually
            open_braces  = cleaned.count("{")
            close_braces = cleaned.count("}")
            cleaned += "}" * (open_braces - close_braces)

            open_brackets  = cleaned.count("[")
            close_brackets = cleaned.count("]")
            cleaned += "]" * (open_brackets - close_brackets)

            try:
                return json.loads(cleaned).get("results", [])
            except:
                raise
    except Exception as e:
        print(f"[LLM ERROR] {e} — flagging all as sensitive")
        return [{"text": c["text"], "sensitive": True,
                 "reason": "LLM unavailable", "label": "Unknown"}
                for c in candidates]

def extract_sensitive_full_text(text: str) -> list:
    try:
        raw = _call_llm(FULL_TEXT_PROMPT + text, max_tokens=1500)
        print("[LLM FULL RAW]", raw)
        raw = _clean_llm_json(raw)
        try:
            return json.loads(raw).get("entities", [])
        except json.JSONDecodeError:
            print("⚠ Full-text JSON truncated, attempting recovery")
            # Try to salvage partial entity list from truncated JSON
            entities = []
            for m in re.finditer(r'\{\s*"text"\s*:\s*"([^"]+)"\s*,\s*"label"\s*:\s*"([^"]+)"', raw):
                entities.append({"text": m.group(1), "label": m.group(2)})
            if entities:
                print(f"[RECOVERY] Salvaged {len(entities)} entities from truncated JSON")
                return entities
            raise
    except Exception as e:
        print(f"[LLM FULL ERROR] {e}")
        return []


# ── Regex candidates ───────────────────────────────────────────────────────────

CANDIDATE_PATTERNS = [
    (r"\b\d{16}\b",                                    "16-digit number"),
    (r"\b\d{12}\b",                                    "12-digit number"),
    (r"\b\d{10}\b",                                    "10-digit number"),
    (r"\b\d{8,}\b",                                    "long number"),
    (r"\b\d{2}/\d{2}/\d{4}\b",                        "date slash"),
    (r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b",              "phone formatted"),
    (r"\b\d{4}[\s\-]\d{4}[\s\-]\d{4}[\s\-]\d{4}\b",  "spaced 16-digit"),
    (r"[A-Z]{5}[0-9]{4}[A-Z]",                        "PAN-like"),
    (r"[2-9][0-9]{11}",                                "Aadhaar-like"),
    (r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", "email"),
    (r"\b[A-Z0-9]{2}[0-9]{6,}\b",  "alphanumeric ID"),   # catches 1D123456789, AB1234567
    (r"\b[A-Z]{1,2}[0-9]{7,}\b",   "license ID"),   
]

def extract_candidates_with_context(text: str, window: int = 60) -> list:
    candidates = []
    seen = set()
    for pattern, _ in CANDIDATE_PATTERNS:
        for m in re.finditer(pattern, text):
            val = m.group().strip()
            if val in seen: continue
            seen.add(val)
            s   = max(0, m.start() - window)
            e   = min(len(text), m.end() + window)
            ctx = text[s:e].replace("\n", " ").strip()
            candidates.append({"text": val, "context": ctx, "start": m.start()})
    return candidates


# ── Main entry ────────────────────────────────────────────────────────────────

def get_all_sensitive_values(text: str):
    # Step 1: full-text LLM (catches names, addresses etc. missed by regex)
    full_text_entities = extract_sensitive_full_text(text)
    llm_full_values = {
        e["text"]: e.get("label", "Unknown")
        for e in full_text_entities
        if isinstance(e, dict) and e.get("text")
    }

    # Step 2: regex candidates + contextual classification
    candidates  = extract_candidates_with_context(text)
    llm_results = classify_with_context(candidates)
    llm_map     = {r["text"]: r for r in llm_results if isinstance(r, dict)}

    sensitive_values = set()
    entities = []

    for val, label in llm_full_values.items():
        sensitive_values.add(val)
        m   = re.search(re.escape(val), text)
        ctx = text[max(0, m.start()-60):min(len(text), m.start()+len(val)+60)] if m else ""
        entities.append({
            "text": val, "context": ctx, "sensitive": True,
            "reason": "Detected via full-text LLM extraction",
            "label": label, "source": "llm-full"
        })

    for c in candidates:
        if c["text"] in sensitive_values: continue
        r    = llm_map.get(c["text"], {})
        is_s = r.get("sensitive", True)
        entities.append({
            "text": c["text"], "context": c["context"], "sensitive": is_s,
            "reason": r.get("reason", ""), "label": r.get("label", "Unknown"),
            "source": "llm+regex"
        })
        if is_s:
            sensitive_values.add(c["text"])

    return list(sensitive_values), entities, len(sensitive_values) > 0

def propose_entities(text: str) -> list:
    _, entities, _ = get_all_sensitive_values(text)
    return entities

def classify_text_only(text: str) -> dict:
    sensitive_values, entities, is_sensitive = get_all_sensitive_values(text)
    redacted = text
    for val in sorted(sensitive_values, key=len, reverse=True):
        redacted = redacted.replace(val, "█" * len(val))
    return {
        "sensitive":     is_sensitive,
        "entity_count":  len(entities),
        "entities":      entities,
        "redacted_text": redacted,
    }
def _clean_llm_json(text: str) -> str:
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*", "", text)
        text = text.rstrip("`").strip()

    return text