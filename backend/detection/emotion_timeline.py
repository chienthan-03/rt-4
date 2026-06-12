# backend/detection/emotion_timeline.py
import json
import logging

from openai import OpenAI

from backend.config import settings
from backend.detection.highlight_detector import Highlight
from backend.llm_json import parse_llm_json

logger = logging.getLogger(__name__)

DRAMATIC = {"shock", "fail", "awkward", "dramatic", "cringe"}
HYPE = {"hype", "funny", "win"}
AMBIENT = {"sadness", "emotional"}
VALID_MOODS = {"chill", "dramatic", "hype", "ambient"}
MIN_SEGMENT_MS = 8000
LLM_DURATION_MS = 120_000
LLM_MIN_HIGHLIGHTS = 3

_client = None


def get_client():
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
    return _client


def emotion_to_mood(emotion: str = "", audience_emotion: str = "") -> str:
    for key in (audience_emotion, emotion):
        k = (key or "").lower()
        if k in DRAMATIC:
            return "dramatic"
        if k in HYPE:
            return "hype"
        if k in AMBIENT:
            return "ambient"
    return "chill"


def _nearest_highlight(highlight: Highlight | None) -> Highlight | None:
    return highlight


def _region_mood(highlights: list[Highlight], region_mid_ms: int) -> str:
    if not highlights:
        return "chill"
    nearest = min(highlights, key=lambda h: abs(h.peak_ms - region_mid_ms))
    return emotion_to_mood(nearest.emotion, nearest.audience_emotion)


def build_emotion_timeline_rule(
    highlights: list[Highlight],
    duration_ms: int,
) -> list[dict]:
    if duration_ms <= 0:
        return []

    sorted_h = sorted(highlights, key=lambda h: h.peak_ms)
    if not sorted_h:
        return [{"start_ms": 0, "end_ms": duration_ms, "mood": "chill", "source": "rule"}]

    boundaries: list[int] = []
    for i in range(len(sorted_h) - 1):
        boundaries.append((sorted_h[i].peak_ms + sorted_h[i + 1].peak_ms) // 2)

    starts = [0] + boundaries
    ends = boundaries + [duration_ms]

    segments: list[dict] = []
    for start_ms, end_ms in zip(starts, ends):
        if end_ms <= start_ms:
            continue
        mid = (start_ms + end_ms) // 2
        segments.append({
            "start_ms": start_ms,
            "end_ms": end_ms,
            "mood": _region_mood(sorted_h, mid),
            "source": "rule",
        })

    segments = _merge_adjacent_mood(segments)
    return merge_short_segments(segments, min_duration_ms=MIN_SEGMENT_MS)


def _merge_adjacent_mood(segments: list[dict]) -> list[dict]:
    if not segments:
        return []
    merged = [segments[0].copy()]
    for seg in segments[1:]:
        if seg["mood"] == merged[-1]["mood"]:
            merged[-1]["end_ms"] = seg["end_ms"]
        else:
            merged.append(seg.copy())
    return merged


def merge_short_segments(segments: list[dict], min_duration_ms: int = MIN_SEGMENT_MS) -> list[dict]:
    if len(segments) <= 1:
        return segments

    result = [s.copy() for s in segments]
    changed = True
    while changed and len(result) > 1:
        changed = False
        i = 0
        while i < len(result):
            dur = result[i]["end_ms"] - result[i]["start_ms"]
            if dur >= min_duration_ms:
                i += 1
                continue
            if i == 0:
                result[i + 1]["start_ms"] = result[i]["start_ms"]
            elif i == len(result) - 1:
                result[i - 1]["end_ms"] = result[i]["end_ms"]
            else:
                left = result[i - 1]["end_ms"] - result[i - 1]["start_ms"]
                right = result[i + 1]["end_ms"] - result[i + 1]["start_ms"]
                if left >= right:
                    result[i - 1]["end_ms"] = result[i]["end_ms"]
                else:
                    result[i + 1]["start_ms"] = result[i]["start_ms"]
            del result[i]
            changed = True
            result = _merge_adjacent_mood(result)
    return result


def _should_use_llm_timeline(duration_ms: int, highlights: list[Highlight]) -> bool:
    return duration_ms > LLM_DURATION_MS or len(highlights) < LLM_MIN_HIGHLIGHTS


def _transcript_excerpt(transcript_segments: list[dict] | None, max_chars: int = 2000) -> str:
    if not transcript_segments:
        return ""
    parts = []
    total = 0
    for seg in transcript_segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        if total + len(text) > max_chars:
            break
        parts.append(text)
        total += len(text)
    return " ".join(parts)


def _llm_emotion_timeline(
    highlights: list[Highlight],
    duration_ms: int,
    transcript_segments: list[dict] | None,
) -> list[dict] | None:
    items = [
        {
            "peak_ms": h.peak_ms,
            "emotion": h.emotion,
            "audience_emotion": h.audience_emotion,
            "context": h.context_text,
        }
        for h in highlights
    ]
    prompt = f"""Chia video thành các đoạn nhạc nền theo cảm xúc.

duration_ms: {duration_ms}
highlights: {json.dumps(items, ensure_ascii=False)}
transcript: {_transcript_excerpt(transcript_segments)}

Trả về JSON array: [{{"start_ms": 0, "end_ms": 30000, "mood": "chill"}}]
mood chỉ được: chill, dramatic, hype, ambient
Phủ từ 0 đến {duration_ms}, không gap, không overlap.
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
        data = parse_llm_json(raw)
    except Exception as exc:
        logger.warning("LLM emotion timeline failed (%s)", exc)
        return None

    segments: list[dict] = []
    for item in data:
        mood = (item.get("mood") or "chill").lower()
        if mood not in VALID_MOODS:
            mood = "chill"
        start_ms = int(item.get("start_ms", 0))
        end_ms = int(item.get("end_ms", duration_ms))
        if end_ms <= start_ms:
            continue
        segments.append({
            "start_ms": max(0, start_ms),
            "end_ms": min(duration_ms, end_ms),
            "mood": mood,
            "source": "llm",
        })

    if not segments:
        return None
    segments.sort(key=lambda s: s["start_ms"])
    return merge_short_segments(_merge_adjacent_mood(segments))


def build_emotion_timeline(
    highlights: list[Highlight],
    duration_ms: int,
    transcript_segments: list[dict] | None = None,
) -> list[dict]:
    rule_segments = build_emotion_timeline_rule(highlights, duration_ms)
    if not _should_use_llm_timeline(duration_ms, highlights):
        return rule_segments
    llm_segments = _llm_emotion_timeline(highlights, duration_ms, transcript_segments)
    return llm_segments if llm_segments else rule_segments
