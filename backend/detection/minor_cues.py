"""Extract Tier 1 (attention) insertion cues from low-level signals."""

from dataclasses import dataclass, field

import numpy as np

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


def extract_speech_pause_cues(
    segments: list[dict],
    min_pause_ms: int = 1500,
    major_highlights: list | None = None,
    major_buffer_ms: int = MAJOR_BUFFER_MS,
) -> list[MinorCue]:
    """Detect gaps > min_pause_ms between transcript segments."""
    major_highlights = major_highlights or []
    major_peaks = [h.peak_ms for h in major_highlights]
    cues: list[MinorCue] = []

    for i in range(len(segments) - 1):
        pause_start = int(segments[i]["end_ms"])
        pause_end = int(segments[i + 1]["start_ms"])
        pause_ms = pause_end - pause_start
        if pause_ms < min_pause_ms:
            continue
        ts = pause_start + pause_ms // 2
        if _near_major_peak(ts, major_peaks, major_buffer_ms):
            continue
        cues.append(
            MinorCue(
                timestamp_ms=ts,
                cue_type="speech_pause",
                score=min(0.5 + pause_ms / 5000.0, 1.0),
                context_text="",
            )
        )
    return cues


def extract_energy_dip_cues(
    rms_segments: list[dict],
    min_dip_duration_ms: int = 1000,
    major_highlights: list | None = None,
    major_buffer_ms: int = MAJOR_BUFFER_MS,
) -> list[MinorCue]:
    """Detect RMS < 20% of video median, lasting > min_dip_duration_ms."""
    if not rms_segments:
        return []

    major_highlights = major_highlights or []
    major_peaks = [h.peak_ms for h in major_highlights]
    median_rms = float(np.median([seg["rms_mean"] for seg in rms_segments]))
    threshold = median_rms * 0.2

    cues: list[MinorCue] = []
    dip_start: int | None = None
    dip_end = 0

    for seg in rms_segments:
        if seg["rms_mean"] < threshold:
            if dip_start is None:
                dip_start = int(seg["start_ms"])
            dip_end = int(seg["end_ms"])
        elif dip_start is not None:
            _maybe_append_dip_cue(
                cues, dip_start, dip_end, min_dip_duration_ms, major_peaks, major_buffer_ms
            )
            dip_start = None

    if dip_start is not None:
        _maybe_append_dip_cue(
            cues, dip_start, dip_end, min_dip_duration_ms, major_peaks, major_buffer_ms
        )
    return cues


def _maybe_append_dip_cue(
    cues: list[MinorCue],
    dip_start: int,
    dip_end: int,
    min_dip_duration_ms: int,
    major_peaks: list[int],
    major_buffer_ms: int,
) -> None:
    duration_ms = dip_end - dip_start
    if duration_ms < min_dip_duration_ms:
        return
    ts = dip_start + duration_ms // 2
    if _near_major_peak(ts, major_peaks, major_buffer_ms):
        return
    cues.append(
        MinorCue(
            timestamp_ms=ts,
            cue_type="energy_dip",
            score=min(0.5 + duration_ms / 4000.0, 1.0),
            context_text="",
        )
    )
