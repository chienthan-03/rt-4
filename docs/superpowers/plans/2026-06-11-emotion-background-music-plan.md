# Emotion-Based Background Music Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add user-controlled continuous background music that spans the full video, changes track per emotional segment, ducks under loud original audio, and ships with a curated starter library.

**Architecture:** Replace RMS-gated single-track background with `emotion_timeline.py` (rule-based + conditional LLM), per-segment selection in `background_selector.py`, refactored placements in `placer.py`, sidechain ducking in `renderer.py`, checkbox on the upload UI, and `sounds/background/` starter pack seeded via `scripts/seed_background_sounds.py`.

**Tech Stack:** Python 3.11, FastAPI, Celery, SQLite, ffmpeg (`sidechaincompress`), OpenRouter LLM (timeline only), Vanilla JS

**Spec:** `docs/superpowers/specs/2026-06-11-emotion-background-music-design.md`

---

## File map

| File | Action | Responsibility |
|------|--------|----------------|
| `backend/detection/emotion_timeline.py` | Create | Rule-based + LLM emotion segments |
| `backend/detection/background_detector.py` | Delete | RMS gate obsolete |
| `backend/sound/background_selector.py` | Modify | `select_background_for_segments()` |
| `backend/placement/placer.py` | Modify | Full-span placements, major dip splits |
| `backend/render/renderer.py` | Modify | Dynamic fades, sidechain duck |
| `tasks.py` | Modify | `enable_background`, new pipeline, result meta |
| `backend/main.py` | Modify | `enable_background` form param |
| `frontend/index.html` | Modify | Checkbox + slider disable |
| `frontend/app.js` | Modify | FormData + toggle handler |
| `frontend/style.css` | Modify | Checkbox styles |
| `sounds/background/manifest.json` | Create | Track sources + mood tags |
| `scripts/seed_background_sounds.py` | Create | Index background folder |
| `tests/test_emotion_timeline.py` | Create | Timeline unit tests |
| `tests/test_background_selector.py` | Create | Per-segment selection tests |
| `tests/test_background_placements.py` | Create | Placement tests |
| `tests/test_renderer.py` | Modify | Duck + dynamic fade tests |
| `tests/test_background_detector.py` | Delete | Replaced by emotion timeline tests |
| `tests/test_main.py` | Modify | `enable_background` API test |

---

### Task 1: Emotion timeline — rule-based core

**Files:**
- Create: `backend/detection/emotion_timeline.py`
- Create: `tests/test_emotion_timeline.py`
- Delete: `backend/detection/background_detector.py`
- Delete: `tests/test_background_detector.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_emotion_timeline.py
from backend.detection.emotion_timeline import (
    emotion_to_mood,
    build_emotion_timeline_rule,
    merge_short_segments,
)
from backend.detection.highlight_detector import Highlight


def test_emotion_to_mood_dramatic():
    assert emotion_to_mood(emotion="shock", audience_emotion="") == "dramatic"
    assert emotion_to_mood(emotion="", audience_emotion="cringe") == "dramatic"


def test_emotion_to_mood_hype():
    assert emotion_to_mood(emotion="funny", audience_emotion="") == "hype"


def test_emotion_to_mood_chill_fallback():
    assert emotion_to_mood(emotion="", audience_emotion="") == "chill"


def test_build_emotion_timeline_two_highlights():
    highlights = [
        Highlight(start_ms=0, end_ms=2000, peak_ms=1000, score=0.9, emotion="funny"),
        Highlight(start_ms=8000, end_ms=10000, peak_ms=9000, score=0.9, emotion="shock"),
    ]
    segments = build_emotion_timeline_rule(highlights, duration_ms=20000)
    assert segments[0]["start_ms"] == 0
    assert segments[-1]["end_ms"] == 20000
    assert any(s["mood"] == "hype" for s in segments)
    assert any(s["mood"] == "dramatic" for s in segments)


def test_merge_short_segments_merges_under_8s():
    segments = [
        {"start_ms": 0, "end_ms": 5000, "mood": "chill", "source": "rule"},
        {"start_ms": 5000, "end_ms": 9000, "mood": "chill", "source": "rule"},
    ]
    merged = merge_short_segments(segments, min_duration_ms=8000)
    assert len(merged) == 1
    assert merged[0]["end_ms"] == 9000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\pytest.exe tests/test_emotion_timeline.py -v`  
Expected: FAIL — `ModuleNotFoundError: emotion_timeline`

- [ ] **Step 3: Implement `emotion_timeline.py`**

```python
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
```

- [ ] **Step 4: Delete obsolete files**

```bash
rm backend/detection/background_detector.py
rm tests/test_background_detector.py
```

- [ ] **Step 5: Run tests**

Run: `.\.venv\Scripts\pytest.exe tests/test_emotion_timeline.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/detection/emotion_timeline.py tests/test_emotion_timeline.py
git rm backend/detection/background_detector.py tests/test_background_detector.py
git commit -m "feat: add emotion timeline for per-segment background mood"
```

---

### Task 2: Per-segment background track selection

**Files:**
- Modify: `backend/sound/background_selector.py`
- Create: `tests/test_background_selector.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_background_selector.py
from unittest.mock import patch

import pytest

from backend.sound.background_selector import select_background_for_segments


MOCK_SOUNDS = [
    {"id": "a1", "tier": "background", "mood": "chill", "file_path": "/bg/chill1.mp3", "name": "chill1"},
    {"id": "a2", "tier": "background", "mood": "chill", "file_path": "/bg/chill2.mp3", "name": "chill2"},
    {"id": "b1", "tier": "background", "mood": "dramatic", "file_path": "/bg/dram1.mp3", "name": "dram1"},
]


@patch("backend.sound.background_selector._background_pool", return_value=MOCK_SOUNDS)
@patch("backend.sound.background_selector.Path")
def test_selects_matching_mood(mock_path, mock_pool):
    mock_path.return_value.is_file.return_value = True
    segments = [
        {"start_ms": 0, "end_ms": 10000, "mood": "chill", "source": "rule"},
        {"start_ms": 10000, "end_ms": 20000, "mood": "dramatic", "source": "rule"},
    ]
    result = select_background_for_segments(segments)
    assert len(result) == 2
    assert result[0]["mood"] == "chill"
    assert result[1]["mood"] == "dramatic"
    assert result[0]["sound_id"] != result[1]["sound_id"] or result[0]["mood"] != result[1]["mood"]


@patch("backend.sound.background_selector._background_pool", return_value=[])
def test_empty_pool_returns_empty(mock_pool):
    segments = [{"start_ms": 0, "end_ms": 10000, "mood": "chill", "source": "rule"}]
    assert select_background_for_segments(segments) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\pytest.exe tests/test_background_selector.py -v`  
Expected: FAIL — `select_background_for_segments` not defined

- [ ] **Step 3: Refactor `background_selector.py`**

Replace `select_background_sound` body; keep function as thin wrapper if needed elsewhere, or remove and update imports.

```python
# backend/sound/background_selector.py
import random
from pathlib import Path

from backend.config import settings
from backend.db.models import get_sounds, init_db
from backend.sound.library import sound_to_selection


def _background_pool(db_path: str | None = None) -> list[dict]:
    db_path = db_path or settings.db_path
    init_db(db_path)
    return [s for s in get_sounds(db_path) if (s.get("tier") or "") == "background"]


def _pick_for_mood(
    pool: list[dict],
    mood: str,
    exclude_ids: set[str],
) -> dict | None:
    mood_matches = [s for s in pool if (s.get("mood") or "chill") == mood]
    candidates = mood_matches or pool
    non_repeat = [s for s in candidates if s["id"] not in exclude_ids]
    if non_repeat:
        candidates = non_repeat
    if not candidates:
        return None
    return random.choice(candidates)


def select_background_for_segments(
    segments: list[dict],
    db_path: str | None = None,
) -> list[dict]:
    pool = _background_pool(db_path)
    if not pool:
        return []

    results: list[dict] = []
    last_id: str | None = None

    for seg in segments:
        sound = _pick_for_mood(pool, seg.get("mood", "chill"), exclude_ids={last_id} if last_id else set())
        if not sound:
            continue
        file_path = sound.get("file_path", "")
        if not file_path or not Path(file_path).is_file():
            continue
        selection = sound_to_selection(sound, reason="background_mood")
        results.append({
            **seg,
            "sound_file": file_path,
            "sound_id": sound["id"],
            "selection": selection,
        })
        last_id = sound["id"]

    return results
```

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\pytest.exe tests/test_background_selector.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/sound/background_selector.py tests/test_background_selector.py
git commit -m "feat: select background track per emotion segment"
```

---

### Task 3: Background placements — full span + major dip

**Files:**
- Modify: `backend/placement/placer.py`
- Create: `tests/test_background_placements.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_background_placements.py
from pathlib import Path
from unittest.mock import patch

from backend.placement.placer import create_background_placements

MAJOR_DIP_MS = 500


@patch.object(Path, "is_file", return_value=True)
def test_full_span_placement(mock_is_file):
    selections = [
        {
            "start_ms": 0,
            "end_ms": 30000,
            "mood": "chill",
            "sound_file": "/bg/chill.mp3",
        }
    ]
    placements = create_background_placements(selections, major_placements=[], duration_ms=30000)
    assert len(placements) == 1
    assert placements[0]["start_ms"] == 0
    assert placements[0]["end_ms"] == 30000
    assert placements[0]["fade_in_ms"] == 500
    assert placements[0]["fade_out_ms"] == 1000
    assert placements[0]["track"] == "background"


@patch.object(Path, "is_file", return_value=True)
def test_splits_before_major(mock_is_file):
    selections = [
        {"start_ms": 0, "end_ms": 20000, "mood": "chill", "sound_file": "/bg/chill.mp3"},
    ]
    major = [{"insert_ms": 10000, "end_ms": 11000}]
    placements = create_background_placements(
        selections, major_placements=major, duration_ms=20000, major_dip_ms=MAJOR_DIP_MS
    )
    assert len(placements) >= 2
    assert all(p["end_ms"] <= 10000 - MAJOR_DIP_MS or p["start_ms"] >= 11000 for p in placements)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\pytest.exe tests/test_background_placements.py -v`  
Expected: FAIL — signature mismatch on `create_background_placements`

- [ ] **Step 3: Replace `create_background_placements` in `placer.py`**

```python
def _split_range_around_majors(
    start_ms: int,
    end_ms: int,
    major_placements: list[dict],
    major_dip_ms: int = 500,
) -> list[tuple[int, int]]:
    ranges = [(start_ms, end_ms)]
    for major in sorted(major_placements, key=lambda p: p["insert_ms"]):
        dip_start = major["insert_ms"] - major_dip_ms
        dip_end = major.get("end_ms", major["insert_ms"] + 1000) + major_dip_ms
        new_ranges: list[tuple[int, int]] = []
        for r_start, r_end in ranges:
            if dip_end <= r_start or dip_start >= r_end:
                new_ranges.append((r_start, r_end))
                continue
            if r_start < dip_start:
                new_ranges.append((r_start, max(r_start, dip_start)))
            if dip_end < r_end:
                new_ranges.append((min(r_end, dip_end), r_end))
        ranges = [(a, b) for a, b in new_ranges if b > a]
    return ranges


def create_background_placements(
    segment_selections: list[dict],
    major_placements: list[dict],
    duration_ms: int,
    bg_volume: float = 0.15,
    major_dip_ms: int = 500,
) -> list[dict]:
    if not segment_selections:
        return []

    placements: list[dict] = []
    for i, seg in enumerate(segment_selections):
        file_path = seg.get("sound_file", "")
        if not file_path or not Path(file_path).is_file():
            continue

        sub_ranges = _split_range_around_majors(
            int(seg["start_ms"]),
            int(seg["end_ms"]),
            major_placements,
            major_dip_ms=major_dip_ms,
        )
        for j, (start_ms, end_ms) in enumerate(sub_ranges):
            if end_ms <= start_ms:
                continue
            fade_in = 500 if start_ms == 0 or j > 0 else 0
            fade_out = 1000 if end_ms == duration_ms else 0
            crossfade = 800 if i > 0 and j == 0 else 0
            placements.append({
                "sound_file": file_path,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "insert_ms": start_ms,
                "volume": bg_volume,
                "fade_in_ms": fade_in,
                "fade_out_ms": fade_out,
                "crossfade_ms": crossfade,
                "track": "background",
            })

    return sorted(placements, key=lambda p: p["start_ms"])
```

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\pytest.exe tests/test_background_placements.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/placement/placer.py tests/test_background_placements.py
git commit -m "feat: full-span background placements with major dip splits"
```

---

### Task 4: Renderer — dynamic fades + sidechain duck

**Files:**
- Modify: `backend/render/renderer.py`
- Modify: `tests/test_renderer.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_renderer.py`:

```python
def test_build_background_filter_parts_uses_dynamic_fade():
    from backend.render.renderer import build_background_filter_parts

    bg_placements = [{
        "sound_file": "/bg/chill.mp3",
        "start_ms": 0,
        "end_ms": 20000,
        "fade_in_ms": 500,
        "fade_out_ms": 1000,
        "crossfade_ms": 0,
    }]
    _, filters, _ = build_background_filter_parts(
        bg_placements, total_duration_s=20.0, start_input_idx=1, bg_volume=0.15
    )
    joined = ";".join(filters)
    assert "afade=t=in:st=0:d=0.5" in joined
    assert "afade=t=out" in joined


def test_build_ffmpeg_filter_includes_sidechain_when_background():
    from backend.render.renderer import build_ffmpeg_filter

    sfx = [{"sound_file": "/a.mp3", "insert_ms": 1000, "volume": 0.5, "fade_out_ms": 0}]
    bg = [{
        "sound_file": "/bg/chill.mp3",
        "start_ms": 0,
        "end_ms": 10000,
        "fade_in_ms": 500,
        "fade_out_ms": 0,
        "crossfade_ms": 0,
        "track": "background",
    }]
    filter_str, _ = build_ffmpeg_filter(sfx, 10.0, bg_placements=bg, bg_volume=0.15)
    assert "sidechaincompress" in filter_str
    assert "[bgducked]" in filter_str
    assert "inputs=3" in filter_str
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\pytest.exe tests/test_renderer.py::test_build_ffmpeg_filter_includes_sidechain_when_background -v`  
Expected: FAIL — no `sidechaincompress`

- [ ] **Step 3: Update `renderer.py`**

Key changes in `build_background_filter_parts`:

```python
fade_in_s = p.get("fade_in_ms", 500) / 1000.0
fade_out_s = p.get("fade_out_ms", 1000) / 1000.0
# use fade_in_s and fade_out_s in afade filters instead of hardcoded 0.5/1.0
```

Add constants and ducking in `build_ffmpeg_filter`:

```python
BG_DUCK_THRESHOLD = 0.018
BG_DUCK_RATIO = 3
BG_DUCK_ATTACK = 50
BG_DUCK_RELEASE = 800

# When both sfx_label and bg_label present:
duck = (
    f"[0:a]asplit=2[aorig][asc];"
    f"[bgall][asc]sidechaincompress=threshold={BG_DUCK_THRESHOLD}:"
    f"ratio={BG_DUCK_RATIO}:attack={BG_DUCK_ATTACK}:release={BG_DUCK_RELEASE}[bgducked];"
    f"[aorig][sfxall][bgducked]amix=inputs=3:duration=first:dropout_transition=0:"
    f"normalize=0:weights=1 1 1,volume=3[aout]"
)
```

Update existing `test_build_background_filter_parts` if fade string assertions change.

- [ ] **Step 4: Run all renderer tests**

Run: `.\.venv\Scripts\pytest.exe tests/test_renderer.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/render/renderer.py tests/test_renderer.py
git commit -m "feat: sidechain duck and dynamic fades for background bus"
```

---

### Task 5: Wire pipeline in `tasks.py`

**Files:**
- Modify: `tasks.py`

- [ ] **Step 1: Add `enable_background` parameter**

```python
def process_video(
    self,
    video_path: str,
    job_id: str,
    major_volume: float = 0.5,
    niche: str = "entertainment",
    minor_volume: float = 0.35,
    bg_volume: float = 0.15,
    enable_background: bool = True,
    meme_volume: float | None = None,
):
```

- [ ] **Step 2: Replace background block**

Remove imports:
```python
from backend.detection.background_detector import ...
from backend.sound.background_selector import select_background_sound
```

Add:
```python
from backend.detection.emotion_timeline import build_emotion_timeline
from backend.sound.background_selector import select_background_for_segments
```

Replace lines 114–124 with:

```python
bg_placements: list[dict] = []
background_warning: str | None = None
background_moods: list[str] = []

if enable_background:
    timeline = build_emotion_timeline(highlights, duration_ms, segments)
    selections = select_background_for_segments(timeline)
    if not selections and timeline:
        background_warning = (
            "Không có nhạc nền trong thư viện — output có thể nghe trống."
        )
    bg_placements = create_background_placements(
        selections,
        major_placements,
        duration_ms=duration_ms,
        bg_volume=bg_volume,
    )
    background_moods = sorted({s.get("mood", "chill") for s in selections})
```

- [ ] **Step 3: Extend result dict**

```python
result = {
  ...
  "background_enabled": enable_background,
  "background_segments": len(bg_placements),
  "background_moods": background_moods,
  "background_warning": background_warning,
}
```

- [ ] **Step 4: Run full test suite**

Run: `.\.venv\Scripts\pytest.exe -v --ignore=tests/test_extractor.py`  
Expected: PASS (fix any broken imports from removed `background_detector`)

- [ ] **Step 5: Commit**

```bash
git add tasks.py
git commit -m "feat: wire emotion-based background pipeline with enable flag"
```

---

### Task 6: API — `enable_background` form param

**Files:**
- Modify: `backend/main.py`
- Modify: `tests/test_main.py`

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.anyio
@patch("backend.main.process_video")
async def test_upload_passes_enable_background(mock_process_video, client, sample_video_path):
    mock_task = MagicMock()
    mock_task.id = "task-bg"
    mock_process_video.delay.return_value = mock_task

    with open(sample_video_path, "rb") as video_file:
        response = await client.post(
            "/upload",
            files={"file": ("test.mp4", video_file, "video/mp4")},
            data={"enable_background": "false"},
        )

    assert response.status_code == 200
    kwargs = mock_process_video.delay.call_args
    assert kwargs[0][6] is False or kwargs[1].get("enable_background") is False
```

Adjust index after verifying positional args: `(video_path, job_id, major, niche, minor, bg, enable_background)`.

- [ ] **Step 2: Update `main.py`**

```python
async def upload_video(
  ...
  enable_background: bool = Form(True),
):
  ...
  task = process_video.delay(
      video_path,
      job_id,
      resolved_major,
      niche,
      minor_volume,
      bg_volume,
      enable_background,
  )
```

- [ ] **Step 3: Fix `test_upload_defaults_volumes`**

Assert `args[6] is True` for default enable_background.

- [ ] **Step 4: Run tests**

Run: `.\.venv\Scripts\pytest.exe tests/test_main.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/main.py tests/test_main.py
git commit -m "feat: add enable_background upload form parameter"
```

---

### Task 7: Frontend checkbox

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/app.js`
- Modify: `frontend/style.css`

- [ ] **Step 1: Add checkbox in `index.html`** (inside volume-controls, before bg slider block)

```html
<div class="bg-enable-control">
  <label class="bg-toggle" for="enableBackgroundCheckbox">
    <input type="checkbox" id="enableBackgroundCheckbox" checked />
    <span>Thêm nhạc nền</span>
  </label>
  <p class="bg-toggle-hint">Nhạc ambient liên tục — tắt nếu chỉ muốn meme sound</p>
</div>
```

- [ ] **Step 2: Update `app.js`**

```javascript
const enableBackgroundCheckbox = document.getElementById('enableBackgroundCheckbox');
const bgVolumeSlider = document.getElementById('bgVolumeSlider');

const getEnableBackground = () => enableBackgroundCheckbox?.checked ?? true;

const syncBgVolumeDisabled = () => {
  if (!bgVolumeSlider) return;
  const enabled = getEnableBackground();
  bgVolumeSlider.disabled = !enabled;
  bgVolumeSlider.setAttribute('aria-disabled', String(!enabled));
  bgVolumeSlider.closest('.volume-control')?.classList.toggle('is-disabled', !enabled);
};

enableBackgroundCheckbox?.addEventListener('change', syncBgVolumeDisabled);
syncBgVolumeDisabled();

// in handleFile:
formData.append('enable_background', getEnableBackground() ? 'true' : 'false');
```

- [ ] **Step 3: Add CSS**

```css
.bg-enable-control { margin-bottom: 0.75rem; }
.bg-toggle { display: flex; align-items: center; gap: 0.5rem; cursor: pointer; }
.bg-toggle-hint { font-size: 0.75rem; color: var(--text-muted); margin: 0.25rem 0 0 1.5rem; }
.volume-control.is-disabled { opacity: 0.4; pointer-events: none; }
```

- [ ] **Step 4: Manual check**

Start server, confirm checkbox defaults on, slider disables when unchecked, FormData includes `enable_background`.

- [ ] **Step 5: Commit**

```bash
git add frontend/index.html frontend/app.js frontend/style.css
git commit -m "feat: add enable background music checkbox to upload UI"
```

---

### Task 8: Starter pack manifest + seed script

**Files:**
- Create: `sounds/background/manifest.json`
- Create: `scripts/seed_background_sounds.py`

- [ ] **Step 1: Curate tracks manually**

Download **≥6 tracks** (≥30s each) from [Mixkit](https://mixkit.co/free-stock-music/) or [Pixabay Music](https://pixabay.com/music/) into `sounds/background/`:

| Filename | Mood |
|----------|------|
| `chill-lofi-01.mp3` | chill |
| `chill-lofi-02.mp3` | chill |
| `dramatic-tension-01.mp3` | dramatic |
| `dramatic-tension-02.mp3` | dramatic |
| `hype-beat-01.mp3` | hype |
| `ambient-pad-01.mp3` | ambient |

Record source URLs in manifest.

- [ ] **Step 2: Create `sounds/background/manifest.json`**

```json
[
  {
    "filename": "chill-lofi-01.mp3",
    "mood": "chill",
    "source_url": "https://mixkit.co/free-stock-music/..."
  }
]
```

- [ ] **Step 3: Create `scripts/seed_background_sounds.py`**

```python
"""Index sounds/background/*.mp3 with tier=background. Usage: python scripts/seed_background_sounds.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from backend.config import settings
from backend.db.models import get_sounds, init_db
from backend.sound.library import add_sound_to_library, get_audio_duration_ms

MANIFEST = Path(settings.sounds_dir) / "background" / "manifest.json"
BG_DIR = Path(settings.sounds_dir) / "background"


def main():
    init_db(settings.db_path)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.is_file() else []
    mood_by_file = {m["filename"]: m.get("mood", "chill") for m in manifest}

    indexed = {str(Path(s["file_path"]).resolve()) for s in get_sounds(settings.db_path)}
    added = 0

    for mp3 in sorted(BG_DIR.glob("*.mp3")):
        resolved = str(mp3.resolve())
        if resolved in indexed:
            print(f"SKIP {mp3.name}")
            continue
        duration_ms = get_audio_duration_ms(str(mp3))
        mood = mood_by_file.get(mp3.name, "chill")
        tag_data = {
            "tier": "background",
            "mood": mood,
            "emotion": mood,
            "intensity": 0.3,
            "timing_type": "buildup",
            "tags": ["background", mood, "ambient"],
            "event_types": ["ambient"],
            "description": f"Background ambient track ({mood})",
        }
        add_sound_to_library(mp3.stem, str(mp3), source_url="", tag_data=tag_data)
        added += 1
        print(f"Added {mp3.name} mood={mood}")

    print(f"Done. Added {added} background sounds.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run seed**

Run: `.\.venv\Scripts\python.exe scripts/seed_background_sounds.py`  
Expected: `Added 6 background sounds.`

- [ ] **Step 5: Verify DB**

Run:
```python
from backend.config import settings
from backend.db.models import get_sounds, init_db
init_db(settings.db_path)
bg = [s for s in get_sounds(settings.db_path) if s.get("tier") == "background"]
print(len(bg), [s.get("mood") for s in bg])
```
Expected: `6 [...]`

- [ ] **Step 6: Commit**

```bash
git add sounds/background/ scripts/seed_background_sounds.py
git commit -m "feat: add background music starter pack and seed script"
```

Note: commit MP3 files only if repo policy allows; otherwise add `sounds/background/*.mp3` to `.gitignore` and document download step in manifest only.

---

### Task 9: Final integration test + full suite

**Files:**
- Modify: `tests/test_emotion_timeline.py` (optional LLM mock test)

- [ ] **Step 1: Add LLM trigger unit test (mocked)**

```python
@patch("backend.detection.emotion_timeline._llm_emotion_timeline", return_value=[{"start_ms": 0, "end_ms": 5000, "mood": "ambient", "source": "llm"}])
def test_build_emotion_timeline_uses_llm_when_sparse(mock_llm):
    from backend.detection.emotion_timeline import build_emotion_timeline
    from backend.detection.highlight_detector import Highlight
    h = [Highlight(start_ms=0, end_ms=1000, peak_ms=500, score=0.9, emotion="funny")]
    segs = build_emotion_timeline(h, duration_ms=30000, transcript_segments=None)
    assert segs[0]["source"] == "llm"
```

- [ ] **Step 2: Run full test suite**

Run: `.\.venv\Scripts\pytest.exe -v`  
Expected: all PASS

- [ ] **Step 3: Manual acceptance**

1. Upload video with checkbox on → `background_segments > 0`, `background_moods` populated.
2. Upload with checkbox off → `background_segments: 0`.
3. Listen: continuous ambient under speech; ducks when original audio loud.

- [ ] **Step 4: Commit**

```bash
git add tests/test_emotion_timeline.py
git commit -m "test: cover LLM emotion timeline trigger path"
```

---

## Spec coverage self-review

| Spec requirement | Task |
|------------------|------|
| Checkbox default on | Task 7 |
| `enable_background` API | Task 6 |
| Emotion timeline hybrid | Task 1 |
| Per-segment track selection | Task 2 |
| Full video span + major dip | Task 3 |
| Sidechain duck | Task 4 |
| Remove RMS gate | Task 1 (delete background_detector) |
| Result metadata + warning | Task 5 |
| Starter pack + seed | Task 8 |
| Tests | Tasks 1–4, 6, 9 |

No gaps. Deferred v2 items (Magnific API, localStorage) intentionally omitted.

---

## Execution handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-11-emotion-background-music-plan.md`.**

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — implement tasks in this session with checkpoints

Which approach?
