from openai import OpenAI
from backend.config import settings

_client = None

def get_client():
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url
        )
    return _client

SHOCK_KEYWORDS = [
    "oh no", "bruh", "wait what", "what the", "no way", "oh my god", "omg",
    "wtf", "noooo", "yikes", "oof", "ouch", "bro", "dude", "seriously",
    "không thể tin", "trời ơi", "ôi trời", "thôi rồi", "chết rồi"
]

def transcribe(audio_path: str) -> dict:
    client = get_client()
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            model=settings.whisper_model,
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["segment"]
        )
    return response.model_dump()

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
