from pathlib import Path

from backend.detection.highlight_detector import Highlight
from backend.detection.minor_cues import MinorCue

MINOR_MIN_GAP_MS = 250
MAJOR_PRIORITY_BUFFER_MS = 300

def calculate_insert_ms(
    peak_ms: int,
    sound_duration_ms: int,
    timing_type: str,
    end_ms: int = None
) -> int:
    if timing_type == "instant":
        return peak_ms - int(sound_duration_ms * 0.1)
    elif timing_type == "reaction":
        base = end_ms if end_ms else peak_ms
        return base + 200
    elif timing_type == "buildup":
        return peak_ms - sound_duration_ms - 300
    return peak_ms

def resolve_overlaps(placements: list[dict], min_gap_ms: int = 500) -> list[dict]:
    placements = sorted(placements, key=lambda p: p["insert_ms"])
    result = []
    for p in placements:
        if not result:
            result.append(p)
            continue
        prev = result[-1]
        if p["insert_ms"] < prev["end_ms"] + min_gap_ms:
            if p.get("confidence", 0) > prev.get("confidence", 0):
                result[-1] = p
        else:
            result.append(p)
    return result

def create_placements(
    highlights: list[Highlight],
    sound_selections: list[dict],
    meme_volume: float = 0.5,
    major_volume: float | None = None,
) -> list[dict]:
    if major_volume is not None:
        meme_volume = major_volume
    placements = []
    for h, sel in zip(highlights, sound_selections):
        if not sel:
            continue
        meta = sel.get("metadata") or {}
        duration_ms = meta.get("duration_ms", 1000)
        timing_type = meta.get("timing_type", "instant")
        file_path = meta.get("file_path", "")
        if not file_path or not Path(file_path).is_file():
            continue

        insert_ms = calculate_insert_ms(h.peak_ms, duration_ms, timing_type, h.end_ms)
        insert_ms = max(0, insert_ms)

        placements.append({
            "sound_file": file_path,
            "insert_ms": insert_ms,
            "end_ms": insert_ms + duration_ms,
            "volume": meme_volume,
            "fade_in_ms": 0,
            "fade_out_ms": 50,
            "confidence": h.impact_score or h.score,
        })

    return resolve_overlaps(placements)


def _overlaps_major(minor_insert_ms: int, minor_end_ms: int, major_placements: list[dict]) -> bool:
    for mp in major_placements:
        start = mp["insert_ms"] - MAJOR_PRIORITY_BUFFER_MS
        end = mp["end_ms"] + MAJOR_PRIORITY_BUFFER_MS
        if minor_insert_ms < end and minor_end_ms > start:
            return True
    return False


def create_minor_placements(
    cues: list[MinorCue],
    sound_selections: list[dict],
    minor_volume: float = 0.35,
) -> list[dict]:
    placements = []

    for cue, sel in zip(cues, sound_selections):
        if not sel:
            continue
        meta = sel.get("metadata") or {}
        duration_ms = min(meta.get("duration_ms", 800), 1200)
        file_path = meta.get("file_path", "")
        if not file_path or not Path(file_path).is_file():
            continue

        insert_ms = max(0, cue.timestamp_ms - 50)
        placements.append({
            "sound_file": file_path,
            "insert_ms": insert_ms,
            "end_ms": insert_ms + duration_ms,
            "volume": minor_volume,
            "fade_in_ms": 0,
            "fade_out_ms": 30,
            "confidence": cue.score,
            "track": "minor",
        })

    return placements


def merge_placements(
    major_placements: list[dict],
    minor_placements: list[dict],
) -> list[dict]:
    """Merge major + minor tracks; majors always win near overlap."""
    for p in major_placements:
        p["track"] = "major"
        p["confidence"] = max(p.get("confidence", 0), 100)

    filtered_minors = []
    for mp in minor_placements:
        if _overlaps_major(mp["insert_ms"], mp["end_ms"], major_placements):
            continue
        filtered_minors.append(mp)

    minors = resolve_overlaps(filtered_minors, min_gap_ms=MINOR_MIN_GAP_MS)
    combined = sorted(major_placements + minors, key=lambda p: p["insert_ms"])
    return combined

def gap_fill_pass(
    placements: list[dict],
    fill_selections: list[dict],
    total_duration_ms: int,
    min_gap_ms: int = 8000,
    filler_volume: float = 0.35,
) -> list[dict]:
    if not fill_selections:
        return sorted(placements, key=lambda p: p["insert_ms"])

    sorted_p = sorted(placements, key=lambda p: p["insert_ms"])
    boundaries: list[tuple[int, int]] = []
    if sorted_p:
        boundaries.append((0, sorted_p[0]["insert_ms"]))
    for i in range(len(sorted_p) - 1):
        boundaries.append((sorted_p[i]["end_ms"], sorted_p[i + 1]["insert_ms"]))
    if sorted_p:
        boundaries.append((sorted_p[-1]["end_ms"], total_duration_ms))
    else:
        boundaries.append((0, total_duration_ms))

    fillers: list[dict] = []
    fill_idx = 0

    for gap_start, gap_end in boundaries:
        gap_dur = gap_end - gap_start
        if gap_dur <= min_gap_ms:
            continue

        num_fillers = gap_dur // min_gap_ms
        spacing = gap_dur // (num_fillers + 1)
        for j in range(1, num_fillers + 1):
            if fill_idx >= len(fill_selections):
                break
            sel = fill_selections[fill_idx]
            meta = sel.get("metadata") or {}
            file_path = meta.get("file_path", "")
            duration_ms = meta.get("duration_ms", 1000)
            fill_idx += 1

            if not file_path or not Path(file_path).is_file():
                continue

            insert_ms = gap_start + spacing * j
            insert_ms = max(0, insert_ms - duration_ms // 2)
            fillers.append({
                "sound_file": file_path,
                "insert_ms": insert_ms,
                "end_ms": insert_ms + duration_ms,
                "volume": filler_volume,
                "fade_in_ms": 100,
                "fade_out_ms": 100,
                "track": "filler",
            })

    return sorted(placements + fillers, key=lambda p: p["insert_ms"])


def create_background_placements(
    bg_selection: dict | None,
    bg_segments: list[dict],
    major_placements: list[dict],
    bg_volume: float = 0.15,
) -> list[dict]:
    if not bg_selection or not bg_segments:
        return []

    meta = bg_selection.get("metadata") or {}
    file_path = meta.get("file_path", "")
    if not file_path or not Path(file_path).is_file():
        return []

    major_sorted = sorted(major_placements, key=lambda p: p["insert_ms"])
    placements: list[dict] = []

    for seg in bg_segments:
        start_ms = int(seg["start_ms"])
        end_ms = int(seg["end_ms"])
        for major in major_sorted:
            if major["insert_ms"] > start_ms:
                end_ms = min(end_ms, major["insert_ms"] - 1000)
                break
        if end_ms <= start_ms:
            continue

        placements.append({
            "sound_file": file_path,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "insert_ms": start_ms,
            "volume": bg_volume,
            "fade_in_ms": 500,
            "fade_out_ms": 1000,
            "track": "background",
        })
    return placements
