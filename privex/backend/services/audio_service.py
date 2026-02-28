"""
Audio redaction service.
Your exact Whisper + LLM + ffmpeg muting logic, wrapped to return structured data.
"""

import re, subprocess, shutil
import whisper as _whisper
from services.llm_service import classify_audio_transcript

_whisper_model = None

def _model():
    global _whisper_model
    if _whisper_model is None:
        print("[INIT] Loading Whisper base model...")
        _whisper_model = _whisper.load_model("base")
    return _whisper_model


# ── Your exact interval utils ──────────────────────────────────────────────────

def merge_intervals(intervals: list) -> list:
    if not intervals: return []
    intervals.sort(key=lambda x: x[0])
    merged = [intervals[0]]
    for cur in intervals[1:]:
        prev = merged[-1]
        if cur[0] <= prev[1]:
            merged[-1] = (prev[0], max(prev[1], cur[1]))
        else:
            merged.append(cur)
    return merged


def normalize_word(text: str) -> str:
    return re.sub(r"[^\w]", "", text).lower()


# ── Your exact numeric + phrase matching ───────────────────────────────────────

def find_mute_ranges(words: list, sensitive_values: list) -> list:
    norm = [normalize_word(w["text"]) for w in words]
    mutes = []

    for value in sensitive_values:
        # Numeric match
        if re.search(r"\d", value):
            target = re.sub(r"\D", "", value)
            for i in range(len(words)):
                collected = ""
                start = words[i]["start"]
                for j in range(i, len(words)):
                    digits = re.sub(r"\D", "", words[j]["text"])
                    if not digits: break
                    collected += digits
                    if collected == target:
                        print(f"[MATCH NUM] '{value}' ({start:.2f}s–{words[j]['end']:.2f}s)")
                        mutes.append((start, words[j]["end"]))
                        break
                    if len(collected) > len(target): break

        # Phrase match
        else:
            tokens = [normalize_word(t) for t in value.split() if normalize_word(t)]
            for i in range(len(words) - len(tokens) + 1):
                if norm[i:i+len(tokens)] == tokens:
                    print(f"[MATCH PHR] '{value}' ({words[i]['start']:.2f}s–{words[i+len(tokens)-1]['end']:.2f}s)")
                    mutes.append((words[i]["start"], words[i+len(tokens)-1]["end"]))
                    break

    return mutes


# ── Main audio redaction ───────────────────────────────────────────────────────

def redact_audio_file(input_path: str, output_path: str) -> dict:
    # Transcribe (your exact params)
    result = _model().transcribe(
        input_path,
        language="en",
        word_timestamps=True,
        fp16=False,
        temperature=0,
        beam_size=5,
        condition_on_previous_text=False,
    )
    transcript = result["text"]
    print(f"[WHISPER] {transcript}")

    words = [
        {"text": w["word"].strip(), "start": w["start"], "end": w["end"]}
        for seg in result["segments"]
        for w in seg.get("words", [])
    ]

    # LLM gets the full transcript — handles spelled-out dates, formatted phones, names
    sensitive_values = classify_audio_transcript(transcript)

    # Regex fallback for anything LLM missed (pure numeric patterns)
    import re as _re
    regex_patterns = [
        r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b",   # 987-654-3210
        r"\b\d{10}\b",                           # 9876543210
        r"\b\d{12,16}\b",                        # account/card numbers
        r"\b\d{2}/\d{2}/\d{4}\b",               # 07/01/1973
    ]
    for pattern in regex_patterns:
        for m in _re.finditer(pattern, transcript):
            val = m.group().strip()
            if val not in sensitive_values:
                sensitive_values.append(val)

    sensitive_values = [v.strip() for v in sensitive_values if v and v.strip()]
    print(f"[AUDIO] Final sensitive values: {sensitive_values}")

    entities = [{"text": v, "source": "llm+audio"} for v in sensitive_values]
    is_sensitive = len(sensitive_values) > 0

    mutes  = find_mute_ranges(words, sensitive_values)
    merged = merge_intervals(mutes)

    # 30ms padding (your exact logic)
    padded = merge_intervals([(max(0, s - 0.03), e + 0.03) for s, e in merged])

    if not padded:
        print("[AUDIO] No sensitive ranges — copying unchanged")
        shutil.copy2(input_path, output_path)
    else:
        # ffmpeg mute (your exact command)
        filter_chain = ",".join(
            f"volume=enable='between(t,{s},{e})':volume=0" for s, e in padded
        )
        subprocess.run(
            ["ffmpeg", "-y", "-i", input_path, "-af", filter_chain, output_path],
            check=True, capture_output=True,
        )

    return {
        "sensitive":      is_sensitive,
        "entity_count":   len(entities),
        "entities":       entities,
        "transcript":     transcript,
        "muted_segments": [{"start": s, "end": e} for s, e in padded],
        "muted_count":    len(padded),
    }
