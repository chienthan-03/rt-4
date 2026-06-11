# Cohesive Audio Layers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a 3-layer cohesive audio system (Major, Minor, Background) with gap-fill logic and UI volume controls to make meme sound insertion feel continuous and professional.

**Architecture:** Modifies detection thresholds, adds two new minor cue extractors (speech pause, energy dip), implements RMS-based background music detection with ffmpeg mixing, introduces gap-fill logic to avoid >8s silences, updates the database schema for background moods, and replaces the single volume slider with three independent sliders on the frontend.

**Tech Stack:** Python, FastAPI, librosa, ffmpeg, Vanilla JS

---

### Task 1: Update Highlight Threshold (Major Layer)

**Files:**
- Modify: `backend/detection/highlight_detector.py`
- Modify: `tests/test_highlight_detector.py`

- [ ] **Step 1: Write the failing test**
```python
def test_detect_highlights_threshold_035():
    # Write a test that ensures highlights with score 0.4 are kept, which would fail under 0.5 threshold
    pass
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_highlight_detector.py`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**
Modify `detect_highlights` default threshold from 0.5 to 0.35 in `backend/detection/highlight_detector.py`.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_highlight_detector.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/detection/highlight_detector.py tests/test_highlight_detector.py
git commit -m "feat: lower highlight detection threshold to 0.35"
```

### Task 2: Fix Timing Offset in Placer

**Files:**
- Modify: `backend/placement/placer.py`
- Modify: `tests/test_placer.py`

- [ ] **Step 1: Write the failing test**
```python
def test_placements_no_double_offset():
    # Test that instant timing type only offsets by 10% of duration and does not subtract an additional anticipation_ms
    pass
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_placer.py`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**
In `backend/placement/placer.py`, remove `anticipation_ms=200` parameter from `create_placements`. Remove the logic that subtracts `anticipation_ms` for `instant` and `buildup` timing types.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_placer.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/placement/placer.py tests/test_placer.py
git commit -m "fix: remove anticipation_ms double-offset in placer"
```

### Task 3: DB Schema and Ingestion Update for Mood

**Files:**
- Modify: `backend/db/models.py`
- Modify: `backend/sound/library.py`
- Modify: `tests/test_db_models.py`

- [ ] **Step 1: Write the failing test**
```python
def test_db_init_adds_mood_column():
    # Create DB, add a sound with mood, retrieve and assert mood is present
    pass
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_db_models.py`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**
In `models.py`, update `CREATE TABLE` and `ALTER TABLE` to add `mood TEXT`. Update `insert_sound` to handle `mood`. In `library.py`, update `add_sound_to_library` and `sound_to_selection` to process `mood`.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_db_models.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/db/models.py backend/sound/library.py tests/test_db_models.py
git commit -m "feat: add mood column to database schema and ingestion logic"
```

### Task 4: Extract RMS Segments

**Files:**
- Modify: `backend/signals/audio_signals.py`
- Modify: `tests/test_audio_signals.py`

- [ ] **Step 1: Write the failing test**
```python
def test_extract_rms_segments():
    # Create dummy audio, test extract_rms_segments returns list of dicts with rms_mean
    pass
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_audio_signals.py`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**
In `backend/signals/audio_signals.py`, add `extract_rms_segments` to calculate RMS mean for 10-second segments using librosa.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_audio_signals.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/signals/audio_signals.py tests/test_audio_signals.py
git commit -m "feat: add extract_rms_segments to audio signals"
```

### Task 5: New Minor Cue Extractors

**Files:**
- Modify: `backend/detection/minor_cues.py`
- Modify: `tests/test_minor_cues.py`

- [ ] **Step 1: Write the failing tests**
```python
def test_extract_speech_pause_cues():
    # Provide segments with gap > 1500ms, expect cue
    pass

def test_extract_energy_dip_cues():
    # Provide RMS segments with dip > 1000ms, expect cue
    pass
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_minor_cues.py`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**
In `backend/detection/minor_cues.py`, implement `extract_speech_pause_cues` and `extract_energy_dip_cues`. Avoid major highlights buffer.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_minor_cues.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/detection/minor_cues.py tests/test_minor_cues.py
git commit -m "feat: add speech_pause and energy_dip cue extractors"
```

### Task 6: Background Detector & Attention Map

**Files:**
- Create: `backend/detection/background_detector.py`
- Modify: `backend/sound/attention_map.py`
- Create: `tests/test_background_detector.py`

- [ ] **Step 1: Write the failing test**
```python
def test_should_use_background():
    # Test with low RMS (>30% silent) returns True, high RMS returns False
    pass
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_background_detector.py`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**
Implement `should_use_background`, `select_background_mood`, and `get_background_segments` using the 0.02 `rms_threshold`. In `backend/sound/attention_map.py`, add mapping `speech_pause` → `["pop", "ding"]` and `energy_dip` → `["ding", "tick"]`.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_background_detector.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/detection/background_detector.py backend/sound/attention_map.py tests/test_background_detector.py
git commit -m "feat: add background detector and update attention map"
```

### Task 7: Gap-Fill & Background Placements

**Files:**
- Modify: `backend/placement/placer.py`
- Modify: `tests/test_placer_gap.py`

- [ ] **Step 1: Write the failing test**
```python
def test_gap_fill_pass():
    # Test gaps > 8000ms are filled with multiple evenly spaced fillers, and gaps < 8000ms are ignored
    pass
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_placer_gap.py`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**
In `backend/placement/placer.py`, implement `gap_fill_pass`. Implement `create_background_placements`. Update `create_minor_placements` signature.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_placer_gap.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/placement/placer.py tests/test_placer_gap.py
git commit -m "feat: add gap fill pass and background placements"
```

### Task 8: Renderer Updates

**Files:**
- Modify: `backend/render/renderer.py`
- Modify: `tests/test_renderer.py`

- [ ] **Step 1: Write the failing test**
```python
def test_build_background_filter_parts():
    # Verify filter contains -stream_loop, atrim, asetpts, and bgall mix
    pass
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_renderer.py`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**
In `backend/render/renderer.py`, implement `build_background_filter_parts` and update `build_ffmpeg_filter` for the background bus and volume mixing.

- [ ] **Step 4: Run test to verify it passes**
Run: `pytest tests/test_renderer.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/render/renderer.py tests/test_renderer.py
git commit -m "feat: update renderer for background track mixing"
```

### Task 9: Backend Tasks Integration

**Files:**
- Modify: `backend/tasks.py`

- [ ] **Step 1: Integrate new pipeline**
Update `process_video` signature to accept `major_volume`, `minor_volume`, `bg_volume`. Combine the 3 minor cue sources. Run gap fill pass. Run background detector and generate placements.

- [ ] **Step 2: Run manual verification**
Verify Celery task processes video without throwing errors.

- [ ] **Step 3: Commit**
```bash
git add backend/tasks.py
git commit -m "feat: integrate 3-layer audio pipeline in tasks.py"
```

### Task 10: Frontend Updates

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/app.js`
- Modify: `frontend/style.css`

- [ ] **Step 1: Update UI layout**
Replace `memeVolumeSlider` with 3 sliders (Major, Minor, Background) in `index.html`. Add corresponding styles in `style.css`. Extract values in `app.js` and update FormData.

- [ ] **Step 2: Commit**
```bash
git add frontend/
git commit -m "feat: update frontend with 3-layer volume sliders"
```

### Task 11: Data Migration Script

**Files:**
- Create: `scripts/backfill_mood.py`

- [ ] **Step 1: Write backfill script**
Create script to auto-tag existing `tier='background'` sounds with a mood. Use existing DB models to fetch and update.

- [ ] **Step 2: Commit**
```bash
git add scripts/backfill_mood.py
git commit -m "feat: add mood backfill script for library"
```
