import json
import logging

from openai import OpenAI

from backend.config import settings
from backend.detection.highlight_detector import Highlight
from backend.detection.impact import apply_impact_fields, should_keep_highlight
from backend.llm_json import parse_llm_json

logger = logging.getLogger(__name__)
_client = None


def get_client():
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
    return _client


def _fallback_validate(highlights: list[Highlight]) -> list[Highlight]:
    result = []
    for h in highlights:
        if h.score < 0.7:
            continue
        apply_impact_fields(
            h,
            importance=3,
            surprise=3,
            emotion_score=3,
            has_punchline=False,
            audience_emotion="",
        )
        if should_keep_highlight(h.impact_score):
            result.append(h)
    return result


def validate_highlights(highlights: list[Highlight]) -> list[Highlight]:
    if not highlights:
        return []

    items = [
        {
            "index": i,
            "peak_ms": h.peak_ms,
            "score": h.score,
            "signals": h.signals,
            "context": h.context_text,
        }
        for i, h in enumerate(highlights)
    ]

    prompt = f"""Bạn đang review các khoảnh khắc trong video để chèn meme sound theo TikTok editor framework.

Danh sách highlights:
{json.dumps(items, ensure_ascii=False, indent=2)}

Với mỗi highlight, chấm điểm và quyết định:
- keep: true/false (có xứng đáng chèn MAJOR meme sound không)
- importance: 1-5 (moment quan trọng đến mức nào)
- surprise: 1-5 (mức bất ngờ)
- emotion_score: 1-5 (cường độ cảm xúc khán giả)
- has_punchline: true/false (có punchline/comedic payoff rõ ràng không)
- audience_emotion: curiosity|surprise|shock|awkward|cringe|hype|sadness|funny|neutral
- event_type: fall|fail|shock|win|awkward|cringe|emotional|funny|plot_twist|generic
- emotion: shock|sadness|hype|fail|awkward|dramatic|funny

Chỉ chèn sound khi importance × surprise × emotion_score >= 30.
Comedy sound chỉ khi impact >= 50 VÀ has_punchline = true.
Ưu tiên đặt sound theo cảm xúc khán giả (tò mò trước punchline), không chỉ theo sự kiện.

Trả về JSON array: [{{"index": 0, "keep": true, "importance": 4, "surprise": 4, "emotion_score": 4, "has_punchline": false, "audience_emotion": "surprise", "event_type": "...", "emotion": "..."}}]
Chỉ trả về JSON array."""

    try:
        client = get_client()
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=2048,
        )
        raw = response.choices[0].message.content or ""
        decisions = parse_llm_json(raw)
    except Exception as e:
        logger.warning("LLM highlight validation failed (%s), using score fallback", e)
        return _fallback_validate(highlights)

    result = []
    for d in decisions:
        if not d.get("keep"):
            continue
        idx = d.get("index")
        if idx is None or idx < 0 or idx >= len(highlights):
            continue
        h = highlights[idx]
        apply_impact_fields(
            h,
            importance=int(d.get("importance", 3)),
            surprise=int(d.get("surprise", 3)),
            emotion_score=int(d.get("emotion_score", 3)),
            has_punchline=bool(d.get("has_punchline", False)),
            audience_emotion=d.get("audience_emotion", ""),
        )
        if not should_keep_highlight(h.impact_score):
            continue
        h.event_type = d.get("event_type", h.event_type)
        h.emotion = d.get("emotion", h.emotion)
        result.append(h)
    return result
