"""Extract Tier 1 (attention) insertion cues from low-level signals."""

from dataclasses import dataclass, field

MAJOR_BUFFER_MS = 2000
MIN_CUE_GAP_MS = 3000
SCENE_MIN_SCORE = 0.42


@dataclass
class MinorCue:
    timestamp_ms: int
    cue_type: str = "scene_change"
    score: float = 0.5
    context_text: str = ""


def _near_major_peak(timestamp_ms: int, major_peak_ms: list[int], buffer_ms: int) -> bool:
    return any(abs(timestamp_ms - peak) < buffer_ms for peak in major_peak_ms)


def extract_minor_cues(
    events: list[dict],
    major_highlights: list | None = None,
    major_buffer_ms: int = MAJOR_BUFFER_MS,
    min_gap_ms: int = MIN_CUE_GAP_MS,
) -> list[MinorCue]:
    """Build minor cues from scene cuts, excluding moments near major highlights."""
    major_highlights = major_highlights or []
    major_peaks = [h.peak_ms for h in major_highlights]

    raw: list[MinorCue] = []
    for ev in events:
        if ev.get("type") != "scene_change":
            continue
        if float(ev.get("score", 0)) < SCENE_MIN_SCORE:
            continue
        ts = int(ev["timestamp_ms"])
        if _near_major_peak(ts, major_peaks, major_buffer_ms):
            continue
        raw.append(
            MinorCue(
                timestamp_ms=ts,
                cue_type="scene_change",
                score=float(ev.get("score", 0.5)),
                context_text=ev.get("context_text", ""),
            )
        )

    raw.sort(key=lambda c: c.timestamp_ms)
    if not raw:
        return []

    kept: list[MinorCue] = [raw[0]]
    for cue in raw[1:]:
        if cue.timestamp_ms - kept[-1].timestamp_ms >= min_gap_ms:
            kept.append(cue)
    return kept
