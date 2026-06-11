# Emotion-Based Background Music — Design Spec

**Date**: 2026-06-11  
**Author**: AI Design Session  
**Status**: Approved by user  
**Supersedes**: Background pass in `2026-06-11-cohesive-audio-layers-design.md` (Section: Tier Background, RMS gate)

---

## Overview

### North star: continuous sound

Video output không chỉ có vài meme rải rác — phải có **âm thanh liên tục** suốt timeline. Nhạc nền (ambient) là lớp glue chính; major/minor/gap-fill vẫn giữ vai trò punchline và texture.

```
Timeline
|----|----|----|----|----|----|----|----|
  🎵🎵🎵🎵🎵🎵🎵🎵🎵🎵🎵🎵🎵🎵🎵🎵   ← background (continuous, low)
     ·  🔉     ·   🔉  ·    🔊         ← minor / filler
              💥              💥        ← major meme
```

### Problems solved

1. Video nghe **trống** giữa các meme — không có lớp ambient liên tục.
2. Logic cũ (`should_use_background`, RMS ≥ 30% im lặng) tắt nhạc nền trên hầu hết video.
3. DB có **0** sound `tier=background` — feature không chạy dù UI có slider.
4. Một track cho cả video — không khớp cảm xúc từng đoạn.
5. User không kiểm soát bật/tắt nhạc nền.

### Solution summary

- Checkbox **“Thêm nhạc nền”** (default **on**).
- Khi bật: phủ **cả video**, duck theo audio gốc, đổi track theo **emotion timeline** (hybrid rule + LLM).
- **Starter pack** nhạc nền royalty-free (Mixkit/Pixabay) — bắt buộc cho v1.
- Xóa RMS 30% gate — user quyết định bật/tắt, không phải heuristic im lặng.

---

## Architecture

```
[Major + Minor + Gap-fill placements]  ← unchanged
       │
       ▼
[enable_background?] ──no──► skip background
       │ yes
       ▼
[build_emotion_timeline]     ← rule-based; LLM if long/sparse
       │
       ▼
[select_background_for_segments]  ← per-segment mood match
       │
       ▼
[create_background_placements]    ← full timeline, major dip
       │
       ▼
[merge all placements]
       │
       ▼
[render: SFX bus + BG bus + sidechain duck + mix]
```

**Integration point** (`tasks.py`): sau `gap_fill_pass`, trước `render_video`.

---

## Section 1: User-facing behavior

### Checkbox

- Label: **“Thêm nhạc nền”**
- Default: **checked**
- Khi unchecked: disable slider nhạc nền; không chạy background pipeline.
- Hint (optional): *“Tắt nhạc nền — video có thể nghe thưa hơn.”*

### Volume slider

- Giữ `bgVolumeSlider` (default 15%).
- Chỉ hoạt động khi checkbox bật.
- Gửi `enable_background` + `bg_volume` lên API.

### Result metadata

```json
{
  "background_enabled": true,
  "background_segments": 3,
  "background_moods": ["chill", "dramatic"],
  "background_warning": null
}
```

Nếu `enable_background=true` nhưng pool trống:

```json
{
  "background_warning": "Không có nhạc nền trong thư viện — output có thể nghe trống."
}
```

---

## Section 2: Emotion timeline (hybrid)

### Module

`backend/detection/emotion_timeline.py`

```python
def build_emotion_timeline(
    highlights: list[Highlight],
    duration_ms: int,
    transcript_segments: list[dict] | None = None,
) -> list[dict]:
    ...
```

### Output shape

```python
{
    "start_ms": int,
    "end_ms": int,
    "mood": str,       # "chill" | "dramatic" | "hype" | "ambient"
    "source": str,     # "rule" | "llm"
}
```

Segments phủ `0 → duration_ms`, không gap, không overlap (sau merge).

### Rule-based (always runs first)

1. Sort highlights by `peak_ms`.
2. Boundaries between highlights = midpoint of adjacent `peak_ms`.
3. First region: `0 → boundary[0]`; middle: `boundary[i] → boundary[i+1]`; last: `boundary[-1] → duration_ms`.
4. Assign mood from nearest highlight:

| `audience_emotion` / `emotion` | Background `mood` |
|--------------------------------|-------------------|
| shock, fail, awkward, dramatic, cringe | `dramatic` |
| hype, funny, win | `hype` |
| sadness, emotional | `ambient` |
| curiosity, surprise, neutral, (empty) | `chill` |

Priority: `audience_emotion` (if set by LLM validator) → `emotion` → `chill`.

5. Merge adjacent segments with same `mood`.
6. Minimum segment duration **8s** — shorter segments merge into neighbor; tie-break: longer neighbor wins.

### LLM timeline (conditional override)

Trigger when **either**:

- `duration_sec > 120`, or
- `len(highlights) < 3`

**Input:** `duration_ms`, highlights (peak_ms, emotion, audience_emotion, context_text), transcript excerpt (max ~2000 chars from whisper segments).

**Output:** JSON `[{start_ms, end_ms, mood}]` — replaces rule-based timeline.

**Fallback:** LLM error or invalid JSON → keep rule-based result.

### Deprecated (remove)

- `should_use_background()` — replaced by user checkbox.
- `get_background_segments()` — no longer RMS-gated placement.

Keep `select_background_mood()` mapping logic in `emotion_timeline.py` or inline; remove from `background_detector.py` if file becomes empty.

---

## Section 3: Track selection & placement

### Track selection

Refactor `backend/sound/background_selector.py`:

```python
def select_background_for_segments(
    segments: list[dict],
    db_path: str | None = None,
) -> list[dict]:
    ...
```

Per segment:

1. Filter `tier == "background"`.
2. Filter by `mood`; fallback to full pool if empty.
3. **Anti-repeat:** do not pick same `sound_id` as previous segment if other candidates exist.
4. **Random** among remaining candidates (not `candidates[0]`).
5. Empty pool → skip segment, log warning.

No LLM for track pick in v1.

### Placement

Refactor `create_background_placements()` in `placer.py`:

**Input:** `segment_selections` (timeline + `sound_file`), `major_placements`, `bg_volume`.

**Per segment → one placement:**

```python
{
    "sound_file": str,
    "start_ms": int,
    "end_ms": int,
    "insert_ms": int,
    "volume": float,
    "fade_in_ms": int,
    "fade_out_ms": int,
    "crossfade_ms": int,
    "track": "background",
}
```

**Fade rules:**

| Case | Behavior |
|------|----------|
| First segment (`start_ms == 0`) | fade in 500ms |
| Last segment (`end_ms == duration`) | fade out 1000ms |
| Boundary, different tracks | crossfade 800ms (overlap in renderer) |
| Same track after mood merge | single long placement |

**Major SFX interaction:**

- At each major `insert_ms`: end background segment early or dip — fade out **500ms** before major.
- Resume fade in **500ms** after major ends (split placement at major boundary).

### tasks.py integration

```python
bg_placements: list[dict] = []
if enable_background:
    timeline = build_emotion_timeline(highlights, duration_ms, segments)
    selections = select_background_for_segments(timeline)
    bg_placements = create_background_placements(
        selections, major_placements, bg_volume=bg_volume
    )
```

---

## Section 4: Ducking & render

### Mix architecture

```
[0:a] original ─────────────────────────┐
[sfxall] meme/minor/filler ─────────────┼─ amix → [aout]
[bgducked] background (sidechained) ────┘
```

### Sidechain ducking

After `[bgall]` bus:

```
[0:a]asplit=2[aorig][asc];
[bgall][asc]sidechaincompress=threshold=0.018:ratio=3:attack=50:release=800[bgducked];
[aorig][sfxall][bgducked]amix=inputs=3:duration=first:dropout_transition=0:normalize=0:weights=1 1 1,volume=3[aout]
```

Constants in `renderer.py` (`BG_DUCK_THRESHOLD`, `BG_DUCK_RATIO`, etc.) — not UI-configurable in v1.

**Fallback:** if `sidechaincompress` unavailable, mix without duck + log warning.

### `build_background_filter_parts` updates

- Read `fade_in_ms`, `fade_out_ms`, `crossfade_ms` from each placement (replace hardcoded 0.5s/1.0s).
- Apply `bg_volume` before sidechain.

### Checkbox off

No BG bus — existing 2-bus mix (original + SFX only).

---

## Section 5: Frontend & API

### `index.html`

Add above bg volume slider:

```html
<label class="bg-toggle">
  <input type="checkbox" id="enableBackgroundCheckbox" checked />
  <span>Thêm nhạc nền</span>
</label>
```

Toggle disables `bgVolumeSlider` when unchecked.

### `app.js`

```javascript
formData.append('enable_background', getEnableBackground() ? 'true' : 'false');
```

### `main.py`

```python
enable_background: bool = Form(True),
```

Pass to `process_video.delay(..., enable_background=enable_background)`.

### `tasks.py`

```python
def process_video(..., bg_volume: float = 0.15, enable_background: bool = True):
```

---

## Section 6: Background music library

### Problem

Current DB: **0** sounds with `tier=background`. MyInstants crawler only provides short meme SFX — not suitable for ambient loops.

### Source strategy (v1): Starter pack + manual folder

**Recommended sources** (royalty-free, commercial OK for mixed video output):

- [Mixkit](https://mixkit.co/free-stock-music/) — hip-hop, lo-fi, playful, cinematic
- [Pixabay Music](https://pixabay.com/music/) — large catalog, mood/genre filters

**Not in v1:** TikTok CML API (for publish-time attachment only, not ffmpeg bake-in). Magnific Music API deferred to v2.

### Directory layout

```
sounds/
  background/
    chill-lofi-01.mp3
    chill-lofi-02.mp3
    dramatic-tension-01.mp3
    dramatic-tension-02.mp3
    hype-beat-01.mp3
    ambient-pad-01.mp3
```

### Minimum library (required for v1 ship)

| Mood | Min tracks |
|------|------------|
| `chill` | 2 |
| `dramatic` | 2 |
| `hype` | 1 |
| `ambient` | 1 |

Tracks should be **≥ 30s**, loop-friendly ambient — not one-shot meme clips.

### Scripts

**`scripts/seed_background_sounds.py`** (new):

- Scan `sounds/background/*.mp3`
- Call `tag_sound()` with prompt suffix: `tier=background`, `mood=chill|dramatic|hype|ambient`
- `add_sound_to_library()` + ChromaDB embedding
- Skip already-indexed paths

**`scripts/backfill_mood.py`** — keep for existing background rows missing mood.

### Schema

No migration — use existing `tier` and `mood` columns.

### License note

Starter pack tracks must be manually curated from Mixkit/Pixabay under their free commercial licenses. Record per-track source URL in `sounds/background/manifest.json` (used by seed script for attribution audit).

---

## Section 7: Testing & acceptance

### Unit tests

| File | Coverage |
|------|----------|
| `tests/test_emotion_timeline.py` | Boundaries, mood mapping, 8s merge, LLM trigger conditions |
| `tests/test_background_selector.py` | Per-segment pick, anti-repeat, empty pool |
| `tests/test_background_placements.py` | Full span, major dip splits, crossfade params |
| `tests/test_renderer.py` | Dynamic fades, `sidechaincompress` in filter string |

### Update / remove

- `tests/test_background_detector.py` → migrate to `test_emotion_timeline.py` or delete RMS tests
- `tests/test_main.py` → `enable_background` param

### Manual acceptance

1. Checkbox on + starter pack → output has continuous background, mood changes by segment.
2. Checkbox off → no background placements (`background_segments: 0`).
3. Loud original audio → background ducks (no double-music clash).
4. Video > 2 min or < 3 highlights → LLM timeline invoked (check logs/meta).
5. Empty pool + checkbox on → `background_warning` in result.
6. Slider disabled when checkbox off.

---

## Relationship to cohesive audio layers

This spec **replaces** the background portions of `2026-06-11-cohesive-audio-layers-design.md`:

| Old | New |
|-----|-----|
| RMS ≥ 30% silent → enable BG | User checkbox (default on) |
| One track, one mood per video | Per-segment mood + track |
| BG only on low-RMS segments | Full video coverage |
| `select_background_sound(mood)` | `select_background_for_segments()` |

Major, minor, gap-fill unchanged.

---

## Open questions (resolved)

- ✅ North star: continuous sound via background layer
- ✅ User control: checkbox default **on**
- ✅ Coverage: full video + sidechain duck
- ✅ Segment mood: hybrid emotion timeline (rule + conditional LLM)
- ✅ Music source v1: starter pack from Mixkit/Pixabay in `sounds/background/`
- ✅ Empty pool: warning in result, no meme-SFX fallback
- ✅ Deprecate: `should_use_background`, `get_background_segments`, RMS 30% gate

## Deferred (v2)

- Magnific Music API crawler for auto-expanding library
- ChromaDB semantic search for background tracks
- UI crossfade/duck strength sliders
- localStorage remember checkbox state
