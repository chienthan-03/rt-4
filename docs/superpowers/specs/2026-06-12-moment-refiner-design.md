# Moment Refiner — Two-Pass Highlight & Timing Design

**Date:** 2026-06-12  
**Status:** Approved by user (brainstorming session)  
**Priority:** A1 (under-detect) + A3 (timing offset)  
**Video types:** V1 talking head, V2 gameplay, V3 reaction  
**Non-goals (this phase):** sound selection, editorial arc, UI changes

---

## 1. Overview

Pipeline hiện tại detect highlight bằng rule-based signals + LLM impact gate, nhưng:

- **A1 — Bỏ lỡ moment:** threshold cao, merge window 2s gộp punchline, face score 0.2, chỉ keyword shock, không có gap scan
- **A3 — Lệch timing:** `peak_ms` = đầu segment/ spike timestamp, offset `timing_type` cố định, không align word/onset/vision

**Giải pháp:** Two-Pass Editor Pipeline

1. **Pass 1 — Wide Recall:** mở rộng signals, hạ threshold, gap scanner → nhiều candidate
2. **Pass 2 — Moment Refiner:** vision LLM trên clip ±1.5s + multi-source timing snap → `refined_insert_ms`
3. **Giữ nguyên:** `llm_validator`, `density_cap`, selector, minor/background, render

**Nguyên tắc:**

- Recall trước, precision sau
- Vision có chọn lọc (≤13 calls/video)
- Density cap chạy **sau** refine
- Feature flag `REFINER_ENABLED` để rollback

---

## 2. Architecture

```
[Signals — mở rộng]
  transcript (word-level events) + audio onset + scene change
  + face_reaction (adaptive fps) + motion_spike (V2)
       │
       ▼
[Pass 1 — wide_recall()]
  merge 1.2s, threshold 0.25, gap scanner
       │
       ▼
[Pass 2 — refine_moments()]
  clip_extractor → vision LLM → timing snap
       │
       ▼
[llm_validator] → [density_cap] → [selector] → [placer]
```

### Pipeline order in `tasks.py`

```python
# 1. Gather signals (extended)
transcript_events = extract_transcript_events(segments)  # pause, emphasis, keyword
audio_events = extract_audio_events(wav_path)
onset_events = extract_onset_events(wav_path)          # NEW in audio_signals.py
visual_events = extract_scene_change_events(frames_dir)
face_events = extract_face_events(frames_dir)
motion_events = extract_motion_events(frames_dir)      # NEW motion_signals.py

all_events = (
    transcript_events + audio_events + onset_events
    + visual_events + face_events + motion_events
)

# 2. Adaptive fps re-extract (V3) — before wide_recall
if face_events:
    frames_dir = reextract_frames_adaptive(
        video_path, frames_dir, face_events, radius_ms=2000, fps=3
    )
    face_events = extract_face_events(frames_dir)  # re-run on denser frames

# 3. Two-pass highlight
candidates = wide_recall(
    all_events, segments, duration_ms,
    transcript_skipped=transcript_skipped,
)
raw_highlights = refine_moments(
    candidates, video_path, wav_path, segments, duration_ms,
    vision_enabled=settings.refiner_vision_enabled,
)
highlights = validate_highlights(raw_highlights)       # editorial impact gate (intentional 2nd LLM)
highlights = apply_density_cap(highlights, duration_sec, niche=niche)
# ... selector, placer unchanged
```

**Double-LLM gate is intentional:** Pass 2 vision answers *"is this a moment and when?"*; `llm_validator` answers *"does it deserve a MAJOR sound?"* — different jobs, not redundant.

### New / modified modules

| Module | Responsibility |
|---|---|
| `moment_refiner.py` | `wide_recall()`, `refine_moments()` orchestration |
| `clip_extractor.py` | Extract 5-frame strip ±1200ms around peak |
| `motion_signals.py` | Frame diff spikes for gameplay |
| `highlight_detector.py` | `MomentCandidate`, extended `Highlight` fields |
| `transcript.py` | pause, sentence_end, emphasis events |
| `face_signals.py` | face_reaction with bbox delta |
| `placer.py` | Use `refined_insert_ms` when present |
| `config.py` | Refiner env settings |

---

## 3. Pass 1 — Wide Recall

### 3.1 Global parameter changes

| Param | Current | New |
|---|---|---|
| `merge_window_ms` | 2000 | 1200 |
| `detect_threshold` | 0.35 | 0.25 |
| Density cap position | After validator | After refine + validator |

### 3.2 Signal expansion by video type

**V1 — Talking head**

| Event | Trigger | Score |
|---|---|---|
| `speech_pause` | Gap between segments > 800ms | 0.35 |
| `sentence_end` | Segment ends with `?` `!` or short segment after long pause | 0.30 |
| `emphasis` | Shock keyword OR segment <1.5s after pause >800ms | 0.40 |

- `peak_ms` = segment `end_ms` (not `start_ms`)
- `context_text` = full segment text

**V2 — Gameplay**

| Event | Trigger | Score |
|---|---|---|
| `motion_spike` | Frame diff > P90 between consecutive frames | 0.45 |
| `audio_onset` | librosa onset strength above threshold | 0.35 |
| `scene_change` | Existing, floor score 0.30 | — |

- `peak_ms` = frame with max diff

**V3 — Reaction**

| Event | Trigger | Score |
|---|---|---|
| `face_reaction` | Face confidence >0.7 AND bbox area change >30% | 0.50 |
| `speech_reaction` | Shock keyword + face within ±1500ms | 0.55 |
| Adaptive fps | Re-extract ±2s at 3fps around face events | — |

### 3.3 Gap scanner

After merging events, scan timeline for gaps > `REFINER_GAP_SCAN_SEC` (default 6s) with no candidate:

- Create `gap_probe` at gap midpoint, score=0.28
- Attach transcript text in gap if available
- Max **3 gap_probe** per video
- When transcript skipped: gap threshold **4s**

### 3.4 Pass 1 output

```python
@dataclass
class MomentCandidate:
    peak_ms: int
    end_ms: int
    score: float
    signals: list[str]
    context_text: str
    source: str          # "merged_event" | "gap_probe"
    video_type_hint: str # "speech" | "action" | "reaction"
```

`video_type_hint` inferred from dominant signal — no user input required.

### 3.5 Transcript skipped fallback

When Whisper returns `skipped: true`:

- `detect_threshold` → **0.20** (from 0.25)
- Boost face/motion event scores × **1.4** (cap 1.0)
- Gap threshold **4s**; always emit up to 3 gap_probes
- API only (no UI work): extend existing `transcript_skipped` / `transcript_note` fields in Celery result

---

## 4. Pass 2 — Moment Refiner

### 4.1 Candidate selection

1. Sort by score desc
2. Dedupe within 1500ms (keep higher score)
3. Take max 10 merged + max 3 gap_probe → **≤13 vision calls**

### 4.2 Clip extraction (`clip_extractor.py`)

Extract 5 JPEG frames at: `[t-1200, t-600, t, t+600, t+1200]` ms

- ffmpeg: `-ss` before `-i` for accurate seek
- Resize max edge 512px
- Base64 encode for OpenRouter multimodal

Include: `context_text`, transcript ±3s, `video_type_hint`

### 4.3 Vision LLM

Model: `REFINER_VISION_MODEL` (default `google/gemini-2.5-flash`)

Prompt varies by `video_type_hint`:

| Hint | Focus |
|---|---|
| `speech` | Punchline, pause before reveal, rhetorical question |
| `action` | Fail/crash/impact, motion peak |
| `reaction` | Face expression, shock moment |

**Required JSON output:**

```json
{
  "keep": true,
  "moment_type": "punchline|fail|reaction|transition|none",
  "optimal_insert_ms": 14200,
  "confidence": 0.85,
  "reason": "short explanation"
}
```

**Pass 2 gates:**

- `keep: false` → drop candidate
- `moment_type: "none"` → **always drop** (regardless of confidence)
- `gap_probe` + `keep: false` → drop

### 4.4 Timing snap

Compute `refined_insert_ms` by priority:

**Speech / punchline:**
1. `word_boundary_ms` — **v1: segment `end_ms`** of the emphasis/punchline segment (no word-level STT; upgrade later if API returns word timestamps)
2. `vision.optimal_insert_ms` if confidence ≥ 0.7
3. `peak_ms`

**Action / fail:**
1. `onset_ms` — nearest librosa onset within ±300ms
2. `vision.optimal_insert_ms` if confidence ≥ 0.7
3. `motion_peak_ms`

**Reaction:**
1. `vision.optimal_insert_ms`
2. `face_reaction_ms`
3. `peak_ms`

**Conflict resolution:**

- Sources disagree >300ms → higher-priority source wins
- Sources disagree ≤150ms → weighted average (vision 0.6, snap 0.4)
- Clamp to `[0, duration_ms - 200]`

**Highlight fields added:**

```python
refined_insert_ms: int | None = None
moment_type: str = ""
refiner_confidence: float = 0.0
```

### 4.5 Placer change

```python
if highlight.refined_insert_ms is not None:
    insert_ms = highlight.refined_insert_ms
else:
    insert_ms = calculate_insert_ms(...)  # legacy fallback
```

No additional offset when `refined_insert_ms` is set.

### 4.6 Fallback when vision fails

| Condition | Behavior |
|---|---|
| API error / timeout | Heuristic snap only, `refiner_confidence = 0.3` |
| Transcript skipped | No word snap; onset + motion; drop gap_probe without strong audio/motion |
| Invalid JSON | Retry once; then heuristic fallback |
| Entire Pass 2 fails | Keep Pass 1 candidates; convert to `Highlight` via `candidates_to_highlights()` using `peak_ms` only (no `refined_insert_ms`); log warning |

### 4.7 Observability

Per-candidate log: `peak_ms, keep, moment_type, sources_used, final_insert_ms, delta_from_peak_ms`

Celery result metadata:

```json
"refiner_stats": {
  "candidates_in": 15,
  "vision_calls": 11,
  "kept": 7,
  "avg_timing_delta_ms": 180
}
```

---

## 5. Configuration

Add to `.env` / `backend/config.py`:

```env
REFINER_ENABLED=true
REFINER_VISION_ENABLED=true
REFINER_VISION_MODEL=google/gemini-2.5-flash
REFINER_MAX_VISION_CALLS=13
REFINER_CLIP_RADIUS_MS=1200
REFINER_MERGE_WINDOW_MS=1200
REFINER_DETECT_THRESHOLD=0.25
REFINER_GAP_SCAN_SEC=6
```

| Flag | Behavior |
|---|---|
| `REFINER_ENABLED=false` | Legacy `detect_highlights(all_events)` — full rollback |
| `REFINER_ENABLED=true`, `REFINER_VISION_ENABLED=false` | **Phase A:** Pass 1 wide recall only, heuristic snap, no vision API |
| Both true | **Phase B:** full two-pass pipeline |

---

## 6. Files to create / modify

| File | Action |
|---|---|
| `backend/detection/moment_refiner.py` | NEW |
| `backend/detection/clip_extractor.py` | NEW |
| `backend/signals/motion_signals.py` | NEW — `extract_motion_events()` |
| `backend/signals/audio_signals.py` | EDIT — `extract_onset_events()` |
| `backend/ingestion/extractor.py` | EDIT — `reextract_frames_adaptive()` |
| `backend/signals/transcript.py` | EDIT |
| `backend/signals/face_signals.py` | EDIT |
| `backend/detection/highlight_detector.py` | EDIT |
| `backend/placement/placer.py` | EDIT |
| `backend/config.py` | EDIT |
| `tasks.py` | EDIT |
| `.env.example` | EDIT |
| `tests/test_moment_refiner.py` | NEW |
| `tests/test_wide_recall.py` | NEW |

---

## 7. MomentCandidate → Highlight conversion

`candidates_to_highlights(candidates)` maps Pass 1/2 output before `validate_highlights()`:

```python
Highlight(
    start_ms=candidate.peak_ms - 500,
    end_ms=candidate.end_ms,
    peak_ms=candidate.peak_ms,
    score=candidate.score,
    event_type=EVENT_TYPE_MAP.get(primary_signal, "generic"),
    emotion=EMOTION_MAP.get(primary_signal, "shock"),
    signals=candidate.signals,
    context_text=candidate.context_text,
    refined_insert_ms=refined_ms,      # from Pass 2 snap, or None
    moment_type=refined_moment_type,
    refiner_confidence=refined_confidence,
)
```

**New signal types** need `EVENT_TYPE_MAP` / `EMOTION_MAP` entries:

| Signal | event_type | emotion |
|---|---|---|
| `speech_pause` | dramatic | dramatic |
| `sentence_end` | generic | shock |
| `emphasis` | shock | shock |
| `motion_spike` | fail | shock |
| `audio_onset` | shock | shock |
| `face_reaction` | funny | funny |
| `speech_reaction` | funny | funny |
| `gap_probe` | generic | shock |

---

## 8. Testing

### Unit tests

| Test | Assert |
|---|---|
| `wide_recall` merge | Events 1.5s apart → 2 separate candidates |
| `wide_recall` gap | 7s gap → 1 gap_probe |
| `wide_recall` speech_pause | 900ms segment gap → event created |
| `timing_snap` speech | word_boundary beats peak_ms |
| `timing_snap` action | onset wins over low-confidence vision |
| `refine_moments` fallback | Vision mock fail → no crash, heuristic used |
| `placer` refined | `refined_insert_ms=5000` → no extra offset |

### Integration test (mock vision)

Fixture 30s video: 2 speech punchlines + 1 scene change  
→ `wide_recall` ≥ 3 candidates  
→ `refine_moments` keeps ≥ 2  
→ placements within ±500ms of expected

### Manual QA

- [ ] V1: punchline after pause detected, timing within 300ms
- [ ] V2: fail/action not missed
- [ ] V3: face reaction caught, timing near expression
- [ ] `REFINER_ENABLED=false` matches legacy behavior

---

## 9. Rollout

| Phase | Scope | Gate |
|---|---|---|
| A | `REFINER_ENABLED=true`, `REFINER_VISION_ENABLED=false` | Unit tests pass |
| B | `REFINER_VISION_ENABLED=true` | Manual QA 3 videos |
| C | Both default true | accept_rate not degraded |

---

## 10. Cost & latency

| | Current | After Phase B |
|---|---|---|
| Cost/video | ~$0.011 | ~$0.04–0.05 |
| Latency | ~60–90s | ~90–130s |
| Vision calls | 0 | ≤13 |

---

## 11. Out of scope

- Sound selection / reaction map / LLM rerank changes
- Minor / background layer changes
- Light Editor UI (only `refiner_stats` in API for debug)
- Model fine-tuning
