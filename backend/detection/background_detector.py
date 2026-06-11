def should_use_background(segments: list[dict], rms_threshold: float = 0.02) -> bool:
    if not segments:
        return False
    silent_duration = sum(seg["end_ms"] - seg["start_ms"] for seg in segments if seg["rms_mean"] < rms_threshold)
    total_duration = sum(seg["end_ms"] - seg["start_ms"] for seg in segments)
    if total_duration == 0:
        return False
    return (silent_duration / total_duration) > 0.3

def select_background_mood() -> str:
    # A placeholder for background mood selection
    return "chill"

def get_background_segments(segments: list[dict], rms_threshold: float = 0.02) -> list[dict]:
    return [seg for seg in segments if seg["rms_mean"] < rms_threshold]
