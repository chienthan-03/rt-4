import json
from openai import OpenAI
from backend.config import settings
from backend.detection.highlight_detector import Highlight

_client = None

def get_client():
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url
        )
    return _client

def _parse_decisions(raw: str) -> list[dict]:
    """Parse LLM JSON response, stripping markdown fences if present."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

def validate_highlights(highlights: list[Highlight]) -> list[Highlight]:
    if not highlights:
        return []

    items = [
        {
            "index": i,
            "peak_ms": h.peak_ms,
            "score": h.score,
            "signals": h.signals,
            "context": h.context_text
        }
        for i, h in enumerate(highlights)
    ]

    prompt = f"""Bạn đang review các khoảnh khắc được phát hiện trong video để chèn meme sound.

Danh sách highlights:
{json.dumps(items, ensure_ascii=False, indent=2)}

Với mỗi highlight, quyết định:
- keep: true/false (có xứng đáng chèn sound không)
- event_type: fall|fail|shock|win|awkward|cringe|emotional|funny|plot_twist|generic
- emotion: shock|sadness|hype|fail|awkward|dramatic|funny

Trả về JSON array: [{{"index": 0, "keep": true, "event_type": "...", "emotion": "..."}}]
Chỉ trả về JSON array."""

    client = get_client()
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    raw = response.choices[0].message.content.strip()
    decisions = _parse_decisions(raw)
    result = []
    for d in decisions:
        if d.get("keep"):
            h = highlights[d["index"]]
            h.event_type = d.get("event_type", h.event_type)
            h.emotion = d.get("emotion", h.emotion)
            result.append(h)
    return result
