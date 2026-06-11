RMS_THRESHOLD = 0.02

DRAMATIC_EMOTIONS = {"shock", "fail", "awkward"}


def should_use_background(segments: list[dict], rms_threshold: float = RMS_THRESHOLD) -> bool:
    if not segments:
        return False
    silent_duration = sum(
        seg["end_ms"] - seg["start_ms"]
        for seg in segments
        if seg["rms_mean"] < rms_threshold
    )
    total_duration = sum(seg["end_ms"] - seg["start_ms"] for seg in segments)
    if total_duration == 0:
        return False
    return (silent_duration / total_duration) >= 0.3


def select_background_mood(highlights: list | None = None) -> str:
    highlights = highlights or []
    for highlight in highlights:
        emotion = getattr(highlight, "emotion", None) or ""
        if emotion in DRAMATIC_EMOTIONS:
            return "dramatic"
    return "chill"


def get_background_segments(segments: list[dict], rms_threshold: float = RMS_THRESHOLD) -> list[dict]:
    return [seg for seg in segments if seg["rms_mean"] < rms_threshold]
