from dataclasses import dataclass, field

EMOTION_MAP = {
    "speech_keyword": "shock",
    "audio_spike": "shock",
    "silence_break": "dramatic",
    "scene_change": "awkward",
    "face_detected": "funny",
}

EVENT_TYPE_MAP = {
    "speech_keyword": "shock",
    "audio_spike": "shock",
    "silence_break": "dramatic",
    "scene_change": "generic",
    "face_detected": "funny",
}

@dataclass
class Highlight:
    start_ms: int
    end_ms: int
    peak_ms: int
    score: float
    event_type: str = "unknown"
    emotion: str = "shock"
    intensity: float = 0.5
    signals: list = field(default_factory=list)
    context_text: str = ""
    importance: int = 3
    surprise: int = 3
    emotion_score: int = 3
    impact_score: int = 27
    has_punchline: bool = False
    audience_emotion: str = ""
    sfx_tier: str = "emphasis"

def merge_events(events: list[dict], window_ms: int = 2000) -> list[dict]:
    if not events:
        return []
    events = sorted(events, key=lambda e: e["timestamp_ms"])
    groups = [[events[0]]]

    for ev in events[1:]:
        if ev["timestamp_ms"] - groups[-1][-1]["timestamp_ms"] <= window_ms:
            groups[-1].append(ev)
        else:
            groups.append([ev])

    merged = []
    for group in groups:
        score = min(sum(e["score"] for e in group), 1.0)
        peak = max(group, key=lambda e: e["score"])
        context = " ".join(e["context_text"] for e in group if e["context_text"]).strip()
        merged.append({
            "timestamp_ms": group[0]["timestamp_ms"],
            "end_ms": group[-1]["timestamp_ms"] + 500,
            "peak_ms": peak["timestamp_ms"],
            "score": score,
            "signals": [e["type"] for e in group],
            "context_text": context
        })
    return merged

def _primary_signal(signals: list[str]) -> str:
    priority = ["speech_keyword", "audio_spike", "silence_break", "face_detected", "scene_change"]
    for signal in priority:
        if signal in signals:
            return signal
    return signals[0] if signals else "audio_spike"


def score_to_highlight(merged_event: dict) -> Highlight:
    primary = _primary_signal(merged_event["signals"])
    return Highlight(
        start_ms=merged_event["timestamp_ms"],
        end_ms=merged_event["end_ms"],
        peak_ms=merged_event["peak_ms"],
        score=merged_event["score"],
        event_type=EVENT_TYPE_MAP.get(primary, "generic"),
        emotion=EMOTION_MAP.get(primary, "shock"),
        intensity=merged_event["score"],
        signals=merged_event["signals"],
        context_text=merged_event["context_text"],
    )

def detect_highlights(all_events: list[dict], threshold: float = 0.5) -> list[Highlight]:
    merged = merge_events(all_events, window_ms=2000)
    return [
        score_to_highlight(e) for e in merged
        if e["score"] >= threshold
    ]
