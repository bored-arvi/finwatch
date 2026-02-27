"""
Audio redaction service.
Your exact Whisper + LLM + ffmpeg muting logic, wrapped to return structured data.
"""

import re, subprocess, shutil
import whisper as _whisper
from services.llm_service import get_all_sensitive_values

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

    sensitive_values, entities, is_sensitive = get_all_sensitive_values(transcript)

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
