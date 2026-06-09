import base64
import logging
import wave
from pathlib import Path

import requests
from backend.config import settings

logger = logging.getLogger(__name__)

SHOCK_KEYWORDS = [
    "oh no", "bruh", "wait what", "what the", "no way", "oh my god", "omg",
    "wtf", "noooo", "yikes", "oof", "ouch", "bro", "dude", "seriously",
    "không thể tin", "trời ơi", "ôi trời", "thôi rồi", "chết rồi"
]

def _audio_duration_s(audio_path: str) -> float:
    with wave.open(audio_path, "rb") as w:
        rate = w.getframerate()
        if rate <= 0:
            return 0.0
        return w.getnframes() / float(rate)

def _transcribe_openrouter(audio_path: str) -> dict:
    """Transcribe via OpenRouter STT API (JSON + base64, not multipart)."""
    path = Path(audio_path)
    audio_format = path.suffix.lstrip(".") or "wav"
    with open(audio_path, "rb") as f:
        b64_audio = base64.b64encode(f.read()).decode("utf-8")

    response = requests.post(
        f"{settings.openrouter_base_url}/audio/transcriptions",
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.whisper_model,
            "input_audio": {"data": b64_audio, "format": audio_format},
        },
        timeout=180,
    )
    response.raise_for_status()
    data = response.json()
    text = (data.get("text") or "").strip()
    segments = data.get("segments")
    if not segments and text:
        duration_s = _audio_duration_s(audio_path)
        segments = [{"start": 0.0, "end": duration_s, "text": text}]
    return {"text": text, "segments": segments or [], "skipped": False}

def transcribe(audio_path: str) -> dict:
    try:
        return _transcribe_openrouter(audio_path)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else None
        if status == 402:
            detail = ""
            try:
                detail = e.response.json().get("error", {}).get("message", "")
            except Exception:
                pass
            logger.warning(
                "OpenRouter audio STT payment required (%s). "
                "Check OPENROUTER_API_KEY in .env matches your funded account.",
                detail or status,
            )
            return {
                "text": "",
                "segments": [],
                "skipped": True,
                "skip_reason": "payment_required",
                "skip_detail": detail,
            }
        raise

def parse_whisper_segments(response: dict) -> list[dict]:
    return [
        {
            "start_ms": int(s["start"] * 1000),
            "end_ms": int(s["end"] * 1000),
            "text": s["text"].strip()
        }
        for s in response.get("segments", [])
    ]

def keyword_score(text: str) -> float:
    text_lower = text.lower()
    score = 0.0
    for kw in SHOCK_KEYWORDS:
        count = text_lower.count(kw)
        if count > 0:
            score += 0.3 * count
    return min(score, 1.0)

def extract_transcript_events(segments: list[dict]) -> list[dict]:
    events = []
    for seg in segments:
        score = keyword_score(seg["text"])
        if score > 0:
            events.append({
                "timestamp_ms": seg["start_ms"],
                "end_ms": seg["end_ms"],
                "score": score,
                "type": "speech_keyword",
                "context_text": seg["text"]
            })
    return events
