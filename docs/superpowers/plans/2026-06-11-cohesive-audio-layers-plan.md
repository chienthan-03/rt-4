# Cohesive Audio Layers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a 3-layer cohesive audio system (Major, Minor, Background) with gap-fill logic and UI volume controls to make meme sound insertion feel continuous and professional.

**Architecture:** Modifies detection thresholds, adds two new minor cue extractors (speech pause, energy dip), implements RMS-based background music detection with ffmpeg mixing, introduces gap-fill logic to avoid >8s silences, and replaces the single volume slider with three independent sliders on the frontend.

**Tech Stack:** Python, FastAPI, librosa, ffmpeg, Vanilla JS

---

### Task 1: Update Highlight Threshold (Major Layer)

**Files:**
- Modify: `backend/detection/highlight_detector.py`
- Modify: `tests/test_highlight_detector.py` (if exists)

- [ ] **Step 1: Modify threshold in highlight detector**
Change the default threshold from 0.5 to 0.35 in `detect_highlights`.

- [ ] **Step 2: Commit**
```bash
git add backend/detection/highlight_detector.py
git commit -m "feat: lower highlight detection threshold to 0.35"
```

### Task 2: Fix Timing Offset in Placer

**Files:**
- Modify: `backend/placement/placer.py`

- [ ] **Step 1: Remove anticipation_ms**
In `backend/placement/placer.py`, remove `anticipation_ms=200` parameter from `create_placements`.
Remove the logic that subtracts `anticipation_ms` for `instant` and `buildup` timing types.

- [ ] **Step 2: Commit**
```bash
git add backend/placement/placer.py
git commit -m "fix: remove anticipation_ms double-offset in placer"
```

### Task 3: Extract RMS Segments

**Files:**
- Modify: `backend/signals/audio_signals.py`

- [ ] **Step 1: Write `extract_rms_segments`**
In `backend/signals/audio_signals.py`, add a function to calculate RMS mean for 10-second segments using librosa. Return list of dicts `[{"start_ms": int, "end_ms": int, "rms_mean": float}]`.

- [ ] **Step 2: Commit**
```bash
git add backend/signals/audio_signals.py
git commit -m "feat: add extract_rms_segments to audio signals"
```

### Task 4: New Minor Cue Extractors

**Files:**
- Modify: `backend/detection/minor_cues.py`

- [ ] **Step 1: Write `extract_speech_pause_cues`**
Detect gaps > 1500ms between transcript segments. Ensure they don't overlap major highlights.

- [ ] **Step 2: Write `extract_energy_dip_cues`**
Detect segments where RMS is < 20% of video median, lasting > 1000ms. Avoid major highlights.

- [ ] **Step 3: Commit**
```bash
git add backend/detection/minor_cues.py
git commit -m "feat: add speech_pause and energy_dip cue extractors"
```

### Task 5: Background Detector & Attention Map

**Files:**
- Create: `backend/detection/background_detector.py`
- Modify: `backend/sound/attention_map.py`

- [ ] **Step 1: Write background detector logic**
Implement `should_use_background`, `select_background_mood`, and `get_background_segments` using the 0.02 `rms_threshold`.

- [ ] **Step 2: Update attention map**
In `backend/sound/attention_map.py`, add mapping `speech_pause` → `["pop", "ding"]` and `energy_dip` → `["ding", "tick"]`.

- [ ] **Step 3: Commit**
```bash
git add backend/detection/background_detector.py backend/sound/attention_map.py
git commit -m "feat: add background detector and update attention map"
```

### Task 6: Gap-Fill & Background Placements

**Files:**
- Modify: `backend/placement/placer.py`

- [ ] **Step 1: Write `gap_fill_pass`**
Implement logic to find >8000ms gaps and insert multiple fillers spaced evenly using `pick_filler_sound()`.

- [ ] **Step 2: Write `create_background_placements`**
Implement logic to generate placements for background segments.
Also, remove `MINOR_VOLUME_RATIO` and `meme_volume` parameter from `create_minor_placements`, adding `minor_volume` parameter with default 0.35.

- [ ] **Step 3: Commit**
```bash
git add backend/placement/placer.py
git commit -m "feat: add gap fill pass and background placements"
```

### Task 7: Renderer Updates

**Files:**
- Modify: `backend/render/renderer.py`

- [ ] **Step 1: Write `build_background_filter_parts`**
Implement ffmpeg filter generation for background tracks (using `-stream_loop -1` input, `atrim`, `asetpts`, `afade`).

- [ ] **Step 2: Update `build_ffmpeg_filter` and `render_video`**
Integrate background bus `[bgall]` with the SFX bus and main audio. Support 3 distinct volumes.

- [ ] **Step 3: Commit**
```bash
git add backend/render/renderer.py
git commit -m "feat: update renderer for background track mixing"
```

### Task 8: Backend Tasks Integration

**Files:**
- Modify: `backend/tasks.py`

- [ ] **Step 1: Integrate new pipeline**
Update `process_video` signature to accept `major_volume`, `minor_volume`, `bg_volume`. Combine the 3 minor cue sources. Run gap fill pass. Run background detector and generate placements. Pass all placements to renderer.

- [ ] **Step 2: Commit**
```bash
git add backend/tasks.py
git commit -m "feat: integrate 3-layer audio pipeline in tasks.py"
```

### Task 9: Frontend Updates

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/app.js`
- Modify: `frontend/style.css`

- [ ] **Step 1: Update UI layout**
Replace `memeVolumeSlider` with 3 sliders (Major, Minor, Background) in `index.html`. Add corresponding styles in `style.css`.

- [ ] **Step 2: Update `app.js`**
Extract values from the 3 sliders and send `major_volume`, `minor_volume`, `bg_volume` in the POST `/upload` FormData.

- [ ] **Step 3: Commit**
```bash
git add frontend/
git commit -m "feat: update frontend with 3-layer volume sliders"
```

### Task 10: Data Migration

**Files:**
- Create: `scripts/backfill_mood.py`

- [ ] **Step 1: Write backfill script**
Create script to `ALTER TABLE sounds ADD COLUMN mood TEXT` if not exists, and auto-tag existing `tier='background'` sounds with a mood.

- [ ] **Step 2: Commit**
```bash
git add scripts/backfill_mood.py
git commit -m "feat: add mood backfill script for library"
```
