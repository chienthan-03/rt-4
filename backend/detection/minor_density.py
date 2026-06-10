"""Density planning for Tier 1 attention SFX."""

from backend.detection.minor_cues import MinorCue
from backend.detection.niche import DEFAULT_NICHE, get_niche_config

WINDOW_MS = 10_000


def max_minor_per_window(niche: str = DEFAULT_NICHE) -> int:
    return get_niche_config(niche)["max_minor_per_window"]


def plan_minor_density(
    cues: list[MinorCue],
    video_duration_sec: float,
    niche: str = DEFAULT_NICHE,
    max_per_window: int | None = None,
    window_ms: int = WINDOW_MS,
) -> list[MinorCue]:
    max_per_window = max_per_window if max_per_window is not None else max_minor_per_window(niche)
    """Cap minor cues to at most `max_per_window` per 10s window (keep highest score)."""
    if not cues or max_per_window <= 0:
        return []

    duration_ms = int(video_duration_sec * 1000)
    num_windows = max(1, (duration_ms + window_ms - 1) // window_ms)
    by_window: dict[int, list[MinorCue]] = {i: [] for i in range(num_windows)}

    for cue in cues:
        window_idx = min(cue.timestamp_ms // window_ms, num_windows - 1)
        by_window[window_idx].append(cue)

    kept: list[MinorCue] = []
    for window_cues in by_window.values():
        ranked = sorted(window_cues, key=lambda c: c.score, reverse=True)
        kept.extend(ranked[:max_per_window])

    return sorted(kept, key=lambda c: c.timestamp_ms)
