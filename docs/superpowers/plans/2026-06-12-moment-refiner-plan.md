# Moment Refiner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement two-pass highlight detection (wide recall + moment refiner) to fix under-detected moments (A1) and timing offset errors (A3) for talking-head, gameplay, and reaction videos.

**Architecture:** Extend signal extraction (transcript pause/emphasis, audio onset, motion spike, face reaction), run `wide_recall()` with gap scanner, optionally refine candidates via vision LLM + multi-source timing snap into `refined_insert_ms`, then feed existing `llm_validator` → `density_cap` → selector → placer. Gated by `REFINER_ENABLED` and `REFINER_VISION_ENABLED`.

**Tech Stack:** Python 3.11+, FastAPI, Celery, librosa, ffmpeg, OpenRouter (Gemini Flash multimodal), pytest

**Spec:** `docs/superpowers/specs/2026-06-12-moment-refiner-design.md`

---

## File map

| File | Responsibility |
|---|---|
| `backend/config.py` | Refiner env settings |
| `backend/detection/highlight_detector.py` | `MomentCandidate`, extended `Highlight`, maps for new signal types |
| `backend/detection/moment_refiner.py` | `wide_recall()`, `refine_moments()`, `timing_snap()`, `candidates_to_highlights()` |
| `backend/detection/clip_extractor.py` | Frame strip extraction + base64 for vision API |
| `backend/signals/transcript.py` | pause, sentence_end, emphasis events |
| `backend/signals/audio_signals.py` | `extract_onset_events()` |
| `backend/signals/motion_signals.py` | `extract_motion_events()` |
| `backend/signals/face_signals.py` | face_reaction with bbox delta |
| `backend/ingestion/extractor.py` | `reextract_frames_adaptive()` |
| `backend/placement/placer.py` | Honor `refined_insert_ms` |
| `tasks.py` | Wire extended signals + two-pass pipeline |
| `.env.example` | Document new env vars |

---

### Task 1: Refiner configuration

**Files:**
- Modify: `backend/config.py`
- Modify: `.env.example`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from backend.config import settings

def test_refiner_settings_defaults():
    assert settings.refiner_enabled is True
    assert settings.refiner_vision_enabled is True
    assert settings.refiner_detect_threshold == 0.25
    assert settings.refiner_merge_window_ms == 1200
    assert settings.refiner_gap_scan_sec == 6
    assert settings.refiner_max_vision_calls == 13
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py::test_refiner_settings_defaults -v`  
Expected: FAIL — attributes missing on `Settings`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/config.py — add to Settings class
refiner_enabled: bool = True
refiner_vision_enabled: bool = True
refiner_vision_model: str = "google/gemini-2.5-flash"
refiner_max_vision_calls: int = 13
refiner_clip_radius_ms: int = 1200
refiner_merge_window_ms: int = 1200
refiner_detect_threshold: float = 0.25
refiner_gap_scan_sec: int = 6
```

Add matching keys to `.env.example`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py::test_refiner_settings_defaults -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/config.py .env.example tests/test_config.py
git commit -m "feat: add moment refiner configuration settings"
```

---

### Task 2: Extend Highlight dataclass and signal maps

**Files:**
- Modify: `backend/detection/highlight_detector.py`
- Modify: `tests/test_highlight_detector.py`

- [ ] **Step 1: Write the failing test**

```python
def test_highlight_has_refiner_fields():
    from backend.detection.highlight_detector import Highlight
    h = Highlight(
        start_ms=0, end_ms=1000, peak_ms=500, score=0.5,
        refined_insert_ms=480, moment_type="punchline", refiner_confidence=0.85,
    )
    assert h.refined_insert_ms == 480
    assert h.moment_type == "punchline"

def test_emotion_map_includes_speech_pause():
    from backend.detection.highlight_detector import EMOTION_MAP, EVENT_TYPE_MAP
    assert EMOTION_MAP["speech_pause"] == "dramatic"
    assert EVENT_TYPE_MAP["motion_spike"] == "fail"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_highlight_detector.py::test_highlight_has_refiner_fields -v`  
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Add to `Highlight`:

```python
refined_insert_ms: int | None = None
moment_type: str = ""
refiner_confidence: float = 0.0
```

Extend `EMOTION_MAP` and `EVENT_TYPE_MAP` per spec §7 table. Update `_primary_signal` priority to include new types:

```python
priority = [
    "speech_reaction", "emphasis", "speech_keyword", "face_reaction",
    "motion_spike", "audio_onset", "audio_spike", "speech_pause",
    "sentence_end", "silence_break", "face_detected", "scene_change", "gap_probe",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_highlight_detector.py -v`  
Expected: PASS (all existing + new tests)

- [ ] **Step 5: Commit**

```bash
git add backend/detection/highlight_detector.py tests/test_highlight_detector.py
git commit -m "feat: extend Highlight with refiner fields and new signal maps"
```

---

### Task 3: MomentCandidate dataclass

**Files:**
- Modify: `backend/detection/highlight_detector.py`
- Create: `tests/test_wide_recall.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_wide_recall.py
from backend.detection.highlight_detector import MomentCandidate

def test_moment_candidate_fields():
    c = MomentCandidate(
        peak_ms=5000, end_ms=5500, score=0.4,
        signals=["emphasis"], context_text="trời ơi",
        source="merged_event", video_type_hint="speech",
    )
    assert c.video_type_hint == "speech"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_wide_recall.py::test_moment_candidate_fields -v`  
Expected: FAIL — `MomentCandidate` not defined

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass
class MomentCandidate:
    peak_ms: int
    end_ms: int
    score: float
    signals: list[str]
    context_text: str
    source: str = "merged_event"
    video_type_hint: str = "speech"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_wide_recall.py::test_moment_candidate_fields -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/detection/highlight_detector.py tests/test_wide_recall.py
git commit -m "feat: add MomentCandidate dataclass"
```

---

### Task 4: Expanded transcript events

**Files:**
- Modify: `backend/signals/transcript.py`
- Create: `tests/test_transcript_events.py`

- [ ] **Step 1: Write the failing test**

```python
from backend.signals.transcript import extract_transcript_events

def test_speech_pause_event():
    segments = [
        {"start_ms": 0, "end_ms": 2000, "text": "hello"},
        {"start_ms": 3000, "end_ms": 4000, "text": "world"},  # 1000ms gap
    ]
    events = extract_transcript_events(segments)
    types = [e["type"] for e in events]
    assert "speech_pause" in types

def test_emphasis_uses_segment_end_as_peak():
    segments = [{"start_ms": 1000, "end_ms": 2500, "text": "trời ơi"}]
    events = extract_transcript_events(segments)
    emphasis = [e for e in events if e["type"] == "emphasis"]
    assert len(emphasis) == 1
    assert emphasis[0]["timestamp_ms"] == 2500  # end_ms as peak
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_transcript_events.py -v`  
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

In `extract_transcript_events`:

1. Keep existing keyword events but set `timestamp_ms = seg["end_ms"]` for emphasis/keyword hits
2. Between consecutive segments, if `next.start_ms - prev.end_ms > 800` → emit `speech_pause` at gap end
3. If segment text ends with `?` or `!` → emit `sentence_end` at `end_ms`
4. If segment follows pause >800ms and duration <1500ms → emit `emphasis`

Each event: `{timestamp_ms, end_ms, score, type, context_text}`

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_transcript_events.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/signals/transcript.py tests/test_transcript_events.py
git commit -m "feat: add speech_pause, sentence_end, emphasis transcript events"
```

---

### Task 5: Audio onset events

**Files:**
- Modify: `backend/signals/audio_signals.py`
- Modify: `tests/test_audio_signals.py`

- [ ] **Step 1: Write the failing test**

```python
def test_extract_onset_events_returns_list(wav_fixture):
    from backend.signals.audio_signals import extract_onset_events
    events = extract_onset_events(wav_fixture)
    assert isinstance(events, list)
    if events:
        assert events[0]["type"] == "audio_onset"
        assert "timestamp_ms" in events[0]
```

Create minimal wav inline in test (no `wav_fixture` in conftest today):

```python
import numpy as np, soundfile as sf  # or wave module
# write 1s sine with burst at 0.5s to tmp_path / "test.wav"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_audio_signals.py::test_extract_onset_events_returns_list -v`  
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
def extract_onset_events(wav_path: str) -> list[dict]:
    y, sr = librosa.load(wav_path, sr=16000, mono=True)
    if len(y) == 0:
        return []
    onset_frames = librosa.onset.onset_detect(y=y, sr=sr, units="frames", backtrack=True)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)
    events = []
    strengths = librosa.onset.onset_strength(y=y, sr=sr)
    for t in onset_times:
        frame = librosa.time_to_frames(t, sr=sr)
        strength = float(strengths[min(frame, len(strengths) - 1)])
        if strength < 0.5:
            continue
        events.append({
            "timestamp_ms": int(t * 1000),
            "score": min(0.35 + strength * 0.3, 1.0),
            "type": "audio_onset",
            "context_text": "",
        })
    return events
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_audio_signals.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/signals/audio_signals.py tests/test_audio_signals.py
git commit -m "feat: add audio onset event extraction"
```

---

### Task 6: Motion spike events

**Files:**
- Create: `backend/signals/motion_signals.py`
- Create: `tests/test_motion_signals.py`

- [ ] **Step 1: Write the failing test**

```python
import numpy as np
import cv2
from pathlib import Path
from backend.signals.motion_signals import extract_motion_events

def test_motion_spike_detected(tmp_path):
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    # Frame 0: blank, Frame 1: white noise = high diff
    cv2.imwrite(str(frames_dir / "frame_0001.jpg"), np.zeros((100, 100, 3), dtype=np.uint8))
    cv2.imwrite(str(frames_dir / "frame_0002.jpg"), np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8))
    events = extract_motion_events(str(frames_dir))
    assert any(e["type"] == "motion_spike" for e in events)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_motion_signals.py -v`  
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
def extract_motion_events(frames_dir: str) -> list[dict]:
    frame_paths = sorted(Path(frames_dir).glob("frame_*.jpg"))
    if len(frame_paths) < 2:
        return []
    diffs = []
    prev = None
    for i, fp in enumerate(frame_paths):
        frame = cv2.imread(str(fp))
        if frame is None:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if prev is not None:
            diff = float(np.mean(cv2.absdiff(prev, gray)))
            diffs.append((i, diff))
        prev = gray
    if not diffs:
        return []
    threshold = float(np.percentile([d for _, d in diffs], 90))
    events = []
    for i, diff in diffs:
        if diff >= threshold and diff > 5.0:
            events.append({
                "timestamp_ms": i * 1000,  # 1fps assumption
                "score": min(0.45 + (diff - threshold) / 50, 1.0),
                "type": "motion_spike",
                "context_text": "",
            })
    return events
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_motion_signals.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/signals/motion_signals.py tests/test_motion_signals.py
git commit -m "feat: add motion spike detection for gameplay moments"
```

---

### Task 7: Face reaction events

**Files:**
- Modify: `backend/signals/face_signals.py`
- Create: `tests/test_face_signals.py`

- [ ] **Step 1: Write the failing test**

```python
def test_face_reaction_type_in_events():
    # Mock or use fixture frames; at minimum test helper exists
    from backend.signals import face_signals
    assert hasattr(face_signals, "extract_face_events")
```

Add integration-style test if model download blocks unit test — use `@patch` on detector.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_face_signals.py -v`  
Expected: FAIL or events lack `face_reaction` type

- [ ] **Step 3: Write minimal implementation**

In `extract_face_events`:

1. Track previous bbox area per frame
2. When face detected with confidence >0.7 AND area change >30% → emit `face_reaction` score 0.50
3. Keep legacy `face_detected` at score 0.2 for backward compat OR replace with face_reaction only when delta threshold met

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_face_signals.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/signals/face_signals.py tests/test_face_signals.py
git commit -m "feat: detect face_reaction events with bbox delta"
```

---

### Task 7b: speech_reaction composite events

**Files:**
- Modify: `backend/detection/moment_refiner.py` (or `backend/signals/composite_signals.py`)
- Modify: `tests/test_wide_recall.py`

- [ ] **Step 1: Write the failing test**

```python
from backend.detection.moment_refiner import build_speech_reaction_events

def test_speech_reaction_when_keyword_and_face_within_1500ms():
    transcript = [{"timestamp_ms": 5000, "end_ms": 5500, "score": 0.4, "type": "emphasis", "context_text": "trời ơi"}]
    faces = [{"timestamp_ms": 5200, "score": 0.5, "type": "face_reaction", "context_text": ""}]
    events = build_speech_reaction_events(transcript, faces)
    assert len(events) == 1
    assert events[0]["type"] == "speech_reaction"
    assert events[0]["score"] == 0.55
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_wide_recall.py::test_speech_reaction_when_keyword_and_face_within_1500ms -v`  
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
def build_speech_reaction_events(transcript_events: list[dict], face_events: list[dict]) -> list[dict]:
    keyword_types = {"speech_keyword", "emphasis", "sentence_end"}
    reactions = []
    for te in transcript_events:
        if te["type"] not in keyword_types:
            continue
        for fe in face_events:
            if abs(fe["timestamp_ms"] - te["timestamp_ms"]) <= 1500:
                reactions.append({
                    "timestamp_ms": max(te["timestamp_ms"], fe["timestamp_ms"]),
                    "end_ms": max(te.get("end_ms", te["timestamp_ms"]), fe.get("end_ms", fe["timestamp_ms"])),
                    "score": 0.55,
                    "type": "speech_reaction",
                    "context_text": te.get("context_text", ""),
                })
                break
    return reactions
```

Call from `tasks.py` before `wide_recall`: append `build_speech_reaction_events(transcript_events, face_events)` to `all_events`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_wide_recall.py::test_speech_reaction_when_keyword_and_face_within_1500ms -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/detection/moment_refiner.py tests/test_wide_recall.py
git commit -m "feat: add speech_reaction composite events for V3 recall"
```

---

### Task 8: wide_recall() — merge, gap scanner, transcript boost

**Files:**
- Create: `backend/detection/moment_refiner.py`
- Modify: `tests/test_wide_recall.py`

- [ ] **Step 1: Write the failing tests**

```python
from backend.detection.moment_refiner import wide_recall

def test_wide_recall_keeps_events_1500ms_apart():
    events = [
        {"timestamp_ms": 1000, "end_ms": 1500, "score": 0.4, "type": "emphasis", "context_text": "a"},
        {"timestamp_ms": 2800, "end_ms": 3200, "score": 0.4, "type": "emphasis", "context_text": "b"},
    ]
    candidates = wide_recall(events, segments=[], duration_ms=10000)
    assert len(candidates) == 2

def test_wide_recall_gap_probe():
    events = [{"timestamp_ms": 1000, "end_ms": 1500, "score": 0.5, "type": "audio_spike", "context_text": ""}]
    candidates = wide_recall(events, segments=[], duration_ms=10000)
    gap_probes = [c for c in candidates if c.source == "gap_probe"]
    assert len(gap_probes) >= 1

def test_wide_recall_transcript_skipped_lowers_threshold():
    events = [{"timestamp_ms": 1000, "end_ms": 1500, "score": 0.22, "type": "motion_spike", "context_text": ""}]
    without = wide_recall(events, segments=[], duration_ms=5000, transcript_skipped=False)
    with_skip = wide_recall(events, segments=[], duration_ms=5000, transcript_skipped=True)
    assert len(with_skip) >= len(without)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_wide_recall.py -v`  
Expected: FAIL — `wide_recall` not defined

- [ ] **Step 3: Write minimal implementation**

```python
# backend/detection/moment_refiner.py
from backend.config import settings
from backend.detection.highlight_detector import MomentCandidate, merge_events

SPEECH_SIGNALS = {"speech_keyword", "emphasis", "speech_pause", "sentence_end", "speech_reaction"}
ACTION_SIGNALS = {"motion_spike", "audio_onset", "audio_spike", "scene_change"}
REACTION_SIGNALS = {"face_reaction", "face_detected", "speech_reaction"}

def infer_video_type_hint(signals: list[str]) -> str:
    if any(s in REACTION_SIGNALS for s in signals):
        return "reaction"
    if any(s in ACTION_SIGNALS for s in signals):
        return "action"
    return "speech"

def _apply_transcript_skipped_boost(events: list[dict]) -> list[dict]:
    boosted = []
    for e in events:
        if e["type"] in ACTION_SIGNALS | REACTION_SIGNALS:
            e = {**e, "score": min(e["score"] * 1.4, 1.0)}
        boosted.append(e)
    return boosted

def _gap_scan(candidates, duration_ms, segments, gap_sec) -> list[MomentCandidate]:
    # Insert up to 3 gap_probe in gaps > gap_sec with no candidate peak inside gap
    # context_text = concatenated segment text whose timestamps fall inside the gap

def wide_recall(events, segments, duration_ms, transcript_skipped=False) -> list[MomentCandidate]:
    threshold = settings.refiner_detect_threshold
    gap_sec = settings.refiner_gap_scan_sec
    if transcript_skipped:
        threshold = 0.20
        gap_sec = 4
        events = _apply_transcript_skipped_boost(events)

    merged = merge_events(events, window_ms=settings.refiner_merge_window_ms)
    candidates = []
    for m in merged:
        if m["score"] < threshold:
            continue
        signals = m["signals"]
        candidates.append(MomentCandidate(
            peak_ms=m["peak_ms"],
            end_ms=m["end_ms"],
            score=m["score"],
            signals=signals,
            context_text=m["context_text"],
            source="merged_event",
            video_type_hint=infer_video_type_hint(signals),
        ))
    return _gap_scan(candidates, duration_ms, segments, gap_sec)
```

Implement `_gap_scan` fully: sort candidate peaks, find gaps, add midpoint probes with score 0.28.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_wide_recall.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/detection/moment_refiner.py tests/test_wide_recall.py
git commit -m "feat: implement wide_recall with gap scanner and transcript fallback"
```

---

### Task 9: timing_snap() heuristic

**Files:**
- Modify: `backend/detection/moment_refiner.py`
- Create: `tests/test_timing_snap.py`

- [ ] **Step 1: Write the failing tests**

```python
from backend.detection.moment_refiner import timing_snap
from backend.detection.highlight_detector import MomentCandidate

def test_timing_snap_speech_prefers_segment_end():
    c = MomentCandidate(peak_ms=1000, end_ms=2500, score=0.4, signals=["emphasis"],
                        context_text="trời ơi", video_type_hint="speech")
    segments = [{"start_ms": 1000, "end_ms": 2500, "text": "trời ơi"}]
    ms, sources = timing_snap(c, segments=segments, vision_result=None, duration_ms=10000)
    assert ms == 2500
    assert "word_boundary" in sources

def test_timing_snap_action_prefers_onset():
    c = MomentCandidate(peak_ms=3000, end_ms=3500, score=0.45, signals=["motion_spike"],
                        context_text="", video_type_hint="action")
    onset_events = [{"timestamp_ms": 2950}]
    ms, sources = timing_snap(c, segments=[], vision_result=None, duration_ms=10000,
                              onset_events=onset_events)
    assert ms == 2950
    assert "onset" in sources
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_timing_snap.py -v`  
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
def timing_snap(candidate, segments, vision_result, duration_ms, onset_events=None):
    sources = []
    vision_ms = None
    if vision_result and vision_result.get("confidence", 0) >= 0.7:
        vision_ms = vision_result.get("optimal_insert_ms")

    if candidate.video_type_hint == "speech":
        word_ms = _segment_end_for_context(candidate, segments)
        if word_ms is not None:
            sources.append("word_boundary")
            base = word_ms
        else:
            base = candidate.peak_ms
        if vision_ms is not None:
            sources.append("vision")
            base = _merge_sources(base, vision_ms, vision_weight=0.6)
        return max(0, min(base, duration_ms - 200)), sources

    # action and reaction branches per spec §4.4
    ...
```

Implement `_segment_end_for_context`, `_nearest_onset`, `_merge_sources` per conflict rules.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_timing_snap.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/detection/moment_refiner.py tests/test_timing_snap.py
git commit -m "feat: add multi-source timing_snap heuristic"
```

---

### Task 10: clip_extractor

**Files:**
- Create: `backend/detection/clip_extractor.py`
- Create: `tests/test_clip_extractor.py`

- [ ] **Step 1: Write the failing test**

```python
from unittest.mock import patch, MagicMock
from backend.detection.clip_extractor import extract_frame_strip_base64

@patch("backend.detection.clip_extractor.subprocess.run")
@patch("builtins.open", create=True)
def test_extract_frame_strip_returns_five_frames(mock_open, mock_run, tmp_path):
    mock_run.return_value = MagicMock(returncode=0)
    mock_open.return_value.__enter__.return_value.read.return_value = b"jpegbytes"
    frames = extract_frame_strip_base64("video.mp4", peak_ms=5000, radius_ms=1200, work_dir=str(tmp_path))
    assert len(frames) == 5
    assert all(isinstance(f, str) for f in frames)  # base64 strings
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_clip_extractor.py -v`  
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

```python
def extract_frame_strip_base64(video_path, peak_ms, radius_ms, work_dir) -> list[str]:
    offsets = [-radius_ms, -radius_ms // 2, 0, radius_ms // 2, radius_ms]
    frames_b64 = []
    for offset in offsets:
        t_ms = max(0, peak_ms + offset)
        out = Path(work_dir) / f"clip_{t_ms}.jpg"
        subprocess.run([
            "ffmpeg", "-y", "-ss", f"{t_ms / 1000:.3f}", "-i", video_path,
            "-frames:v", "1", "-vf", "scale=512:-1", str(out),
        ], check=True, capture_output=True)
        frames_b64.append(base64.b64encode(out.read_bytes()).decode())
    return frames_b64
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_clip_extractor.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/detection/clip_extractor.py tests/test_clip_extractor.py
git commit -m "feat: add clip frame strip extractor for vision refiner"
```

---

### Task 11: refine_moments() with mocked vision

**Files:**
- Modify: `backend/detection/moment_refiner.py`
- Modify: `tests/test_moment_refiner.py` (create)

- [ ] **Step 1: Write the failing tests**

```python
from unittest.mock import patch
from backend.detection.moment_refiner import refine_moments, candidates_to_highlights
from backend.detection.highlight_detector import MomentCandidate

@patch("backend.detection.moment_refiner._call_vision_llm")
def test_refine_moments_drops_moment_type_none(mock_vision):
    mock_vision.return_value = {"keep": True, "moment_type": "none", "confidence": 0.95}
    c = MomentCandidate(peak_ms=1000, end_ms=1500, score=0.5, signals=["emphasis"],
                        context_text="hi", video_type_hint="speech")
    highlights, stats = refine_moments([c], video_path="v.mp4", wav_path="a.wav",
                                       segments=[], duration_ms=5000, vision_enabled=True)
    assert highlights == []

@patch("backend.detection.moment_refiner._call_vision_llm")
def test_refine_moments_drops_rejected(mock_vision):
    mock_vision.return_value = {"keep": False, "moment_type": "none", "confidence": 0.9}
    c = MomentCandidate(peak_ms=1000, end_ms=1500, score=0.5, signals=["emphasis"],
                        context_text="hi", video_type_hint="speech")
    highlights, _ = refine_moments([c], video_path="v.mp4", wav_path="a.wav",
                                    segments=[], duration_ms=5000, vision_enabled=True)
    assert highlights == []

@patch("backend.detection.moment_refiner._call_vision_llm")
def test_refine_moments_sets_refined_insert_ms(mock_vision):
    mock_vision.return_value = {
        "keep": True, "moment_type": "punchline",
        "optimal_insert_ms": 2400, "confidence": 0.9, "reason": "ok",
    }
    c = MomentCandidate(peak_ms=1000, end_ms=2500, score=0.5, signals=["emphasis"],
                        context_text="trời ơi", video_type_hint="speech")
    segments = [{"start_ms": 1000, "end_ms": 2500, "text": "trời ơi"}]
    highlights, stats = refine_moments([c], video_path="v.mp4", wav_path="a.wav",
                                       segments=segments, duration_ms=10000, vision_enabled=True)
    assert len(highlights) == 1
    assert highlights[0].refined_insert_ms is not None
    assert highlights[0].moment_type == "punchline"
    assert stats["vision_calls"] == 1

def test_refine_moments_vision_disabled_uses_heuristic_only():
    c = MomentCandidate(peak_ms=1000, end_ms=2500, score=0.5, signals=["emphasis"],
                        context_text="x", video_type_hint="speech")
    segments = [{"start_ms": 1000, "end_ms": 2500, "text": "x"}]
    highlights, stats = refine_moments([c], video_path="v.mp4", wav_path="a.wav",
                                       segments=segments, duration_ms=10000, vision_enabled=False)
    assert len(highlights) == 1
    assert highlights[0].refined_insert_ms == 2500
    assert stats["vision_calls"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_moment_refiner.py -v`  
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

**Return type:** `refine_moments(...) -> tuple[list[Highlight], dict]`

```python
refiner_stats = {
    "candidates_in": len(candidates),
    "vision_calls": 0,
    "kept": 0,
    "avg_timing_delta_ms": 0,
}
```

Key functions in `moment_refiner.py`:

- `_select_candidates_for_vision()` — dedupe 1500ms, cap 10 merged + 3 gap_probe
- `_call_vision_llm()` — OpenRouter multimodal (match `llm_validator.get_client()` pattern):

```python
content = [{"type": "text", "text": prompt}]
for b64 in frames_b64:
    content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
response = client.chat.completions.create(
    model=settings.refiner_vision_model,
    messages=[{"role": "user", "content": content}],
    response_format={"type": "json_object"},
)
```

- Parse via `parse_llm_json`; retry once on invalid JSON
- **Gates:** `keep: false` → drop; `moment_type == "none"` → always drop
- `candidates_to_highlights()` — map kept candidates to `Highlight`
- Load `onset_events = extract_onset_events(wav_path)` inside `refine_moments` (or accept param)

**Transcript skipped branch (spec §4.6):**
- No word_boundary snap in `timing_snap`
- Drop `gap_probe` unless candidate has `motion_spike` or `audio_onset`/`audio_spike` in signals

**Entire Pass 2 fail:** return `candidates_to_highlights(candidates, vision_results={})` with empty `refined_insert_ms`

When `vision_enabled=False`: skip `_call_vision_llm`, run `timing_snap` with `vision_result=None` for all candidates.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_moment_refiner.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/detection/moment_refiner.py tests/test_moment_refiner.py
git commit -m "feat: implement refine_moments with vision mock and heuristic fallback"
```

---

### Task 12: Adaptive frame re-extract

**Files:**
- Modify: `backend/ingestion/extractor.py`
- Create: `tests/test_extractor_adaptive.py`

- [ ] **Step 1: Write the failing test**

```python
from unittest.mock import patch
from backend.ingestion.extractor import reextract_frames_adaptive

@patch("backend.ingestion.extractor.subprocess.run")
def test_reextract_frames_adaptive_calls_ffmpeg(mock_run, tmp_path):
    face_events = [{"timestamp_ms": 5000}]
    out = reextract_frames_adaptive(
        "video.mp4", str(tmp_path), face_events, radius_ms=2000, fps=3,
    )
    assert mock_run.called
    assert out == str(tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_extractor_adaptive.py -v`  
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

For each face event at `t_ms`:

1. Extract to `{frames_dir}/adaptive_{t_ms}/frame_%04d.jpg` with:
   `ffmpeg -ss {(t_ms-radius)/1000} -i video -t {2*radius/1000} -vf fps=3`
2. Copy adaptive frames into main `frames_dir` using timestamp-based names:
   `frame_{int(t_sec):04d}_{subframe:02d}.jpg` where `subframe` = 0..2 per second
3. Update `extract_face_events` / `extract_motion_events` to sort by parsed timestamp from filename (fallback: index × 333ms for adaptive frames)

Document filename convention in `extractor.py` docstring.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_extractor_adaptive.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/ingestion/extractor.py tests/test_extractor_adaptive.py
git commit -m "feat: add adaptive fps frame re-extract around face events"
```

---

### Task 13: Placer honors refined_insert_ms

**Files:**
- Modify: `backend/placement/placer.py`
- Modify: `tests/test_placer.py`

- [ ] **Step 1: Write the failing test**

```python
def test_create_placements_uses_refined_insert_ms(tmp_path):
    sound_file = tmp_path / "test.mp3"
    sound_file.write_bytes(b"ID3")
    h = Highlight(
        start_ms=0, end_ms=2000, peak_ms=1000, score=0.8,
        refined_insert_ms=5000,
    )
    sel = {"chosen_id": "x", "metadata": {
        "file_path": str(sound_file), "duration_ms": 1000, "timing_type": "instant",
    }}
    placements = create_placements([h], [sel])
    assert placements[0]["insert_ms"] == 5000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_placer.py::test_create_placements_uses_refined_insert_ms -v`  
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

In `create_placements` loop:

```python
if getattr(h, "refined_insert_ms", None) is not None:
    insert_ms = h.refined_insert_ms
else:
    insert_ms = calculate_insert_ms(h.peak_ms, duration_ms, timing_type, h.end_ms)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_placer.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/placement/placer.py tests/test_placer.py
git commit -m "feat: placer uses refined_insert_ms when set by moment refiner"
```

---

### Task 14: Wire pipeline in tasks.py

**Files:**
- Modify: `tasks.py`
- Modify: `tests/test_tasks_pipeline.py` (create if needed)

- [ ] **Step 1: Write the failing test**

```python
from unittest.mock import patch, MagicMock
from backend.config import settings

@patch("backend.detection.moment_refiner.refine_moments")
@patch("backend.detection.moment_refiner.wide_recall")
@patch("backend.detection.highlight_detector.detect_highlights")
def test_refiner_enabled_calls_wide_recall(mock_detect, mock_wide, mock_refine):
    mock_wide.return_value = []
    mock_refine.return_value = ([], {"candidates_in": 0, "vision_calls": 0, "kept": 0, "avg_timing_delta_ms": 0})
    # invoke pipeline helper or patch process_video at signal-gather point
    mock_wide.assert_called_once()
    mock_detect.assert_not_called()

@patch("backend.detection.highlight_detector.detect_highlights")
def test_refiner_disabled_uses_legacy_detect(mock_detect):
    mock_detect.return_value = []
    # when settings.refiner_enabled=False, detect_highlights called, wide_recall not
    mock_detect.assert_called_once()
```

Use patch on `backend.detection.moment_refiner.wide_recall` and `refine_moments`. Extract signal-gather + highlight block into `_detect_highlights_pipeline(...)` in `tasks.py` to make unit-testable without running full Celery task.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tasks_pipeline.py -v`  
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Replace highlight detection block in `process_video`:

```python
from backend.detection.highlight_detector import detect_highlights
from backend.detection.moment_refiner import wide_recall, refine_moments
from backend.signals.audio_signals import extract_onset_events
from backend.signals.motion_signals import extract_motion_events
from backend.ingestion.extractor import reextract_frames_adaptive

onset_events = extract_onset_events(wav_path)
motion_events = extract_motion_events(frames_dir)
all_events = transcript_events + audio_events + onset_events + visual_events + face_events + motion_events

if settings.refiner_enabled:
    if face_events:
        frames_dir = reextract_frames_adaptive(video_path, frames_dir, face_events)
        face_events = extract_face_events(frames_dir)
        # rebuild motion after re-extract
        motion_events = extract_motion_events(frames_dir)
        all_events = transcript_events + audio_events + onset_events + visual_events + face_events + motion_events

    candidates = wide_recall(all_events, segments, duration_ms, transcript_skipped=transcript_skipped)
    raw_highlights, refiner_stats = refine_moments(
        candidates, video_path, wav_path, segments, duration_ms,
        vision_enabled=settings.refiner_vision_enabled,
        transcript_skipped=transcript_skipped,
    )
else:
    raw_highlights = detect_highlights(all_events)
    refiner_stats = None
```

Add `refiner_stats` to Celery result dict when not None.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_tasks_pipeline.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tasks.py tests/test_tasks_pipeline.py
git commit -m "feat: wire moment refiner two-pass pipeline in process_video"
```

---

### Task 15: Full test suite + manual QA gate

**Files:**
- All test files

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v`  
Expected: All PASS

- [ ] **Step 2: Phase A smoke test**

Set `.env`: `REFINER_ENABLED=true`, `REFINER_VISION_ENABLED=false`  
Restart Celery worker. Upload a talking-head test video.  
Expected: more placements than before; `refiner_stats` in job result.

- [ ] **Step 3: Phase B smoke test**

Set `REFINER_VISION_ENABLED=true`  
Upload gameplay + reaction test videos.  
Expected: timing feels closer to punchline; vision calls ≤13 in `refiner_stats`.

- [ ] **Step 4: Rollback verify**

Set `REFINER_ENABLED=false`  
Expected: behavior matches pre-refiner baseline.

- [ ] **Step 5: Commit any test fixes**

```bash
git add -A
git commit -m "test: verify moment refiner phase A/B and rollback"
```

---

## Rollout checklist

- [ ] Phase A: `REFINER_VISION_ENABLED=false` — ship wide recall + heuristic snap
- [ ] Phase B: enable vision after manual QA on V1/V2/V3 sample videos
- [ ] Phase C: both flags default true in `.env.example`

## Out of scope (do not implement in this plan)

- Sound selection / reaction map changes
- Minor / background layer changes
- Light Editor UI (only `refiner_stats` in API response)
