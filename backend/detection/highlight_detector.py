from dataclasses import dataclass, field

EMOTION_MAP = {
    "speech_keyword": "shock",
    "audio_spike": "shock",
    "silence_break": "dramatic",
    "scene_change": "neutral",
    "face_detected": "neutral"
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

def score_to_highlight(merged_event: dict) -> Highlight:
    return Highlight(
        start_ms=merged_event["timestamp_ms"],
        end_ms=merged_event["end_ms"],
        peak_ms=merged_event["peak_ms"],
        score=merged_event["score"],
        intensity=merged_event["score"],
        signals=merged_event["signals"],
        context_text=merged_event["context_text"]
    )

def detect_highlights(all_events: list[dict], threshold: float = 0.5) -> list[Highlight]:
    merged = merge_events(all_events, window_ms=2000)
    return [
        score_to_highlight(e) for e in merged
        if e["score"] >= threshold
    ]
