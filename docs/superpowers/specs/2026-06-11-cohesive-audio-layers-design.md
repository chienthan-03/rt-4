# Cohesive Audio Layers — Design Spec
**Date**: 2026-06-11
**Author**: AI Design Session
**Status**: Approved by user

---

## Overview

Hệ thống sound hiện tại cảm giác "tách rời và ít" — sound xuất hiện rời rạc, không phân biệt rõ vai trò major/minor, không có gì nối giữa các khoảnh khắc. Feature này tái cấu trúc audio pipeline thành 3 tầng rõ ràng với logic kích hoạt độc lập, đảm bảo video output dày đặc và mạch lạc về mặt âm thanh.

**4 vấn đề được giải quyết:**
1. Quá ít sound (video 2 phút chỉ 2-3 sound)
2. Sound chính và phụ không có vai trò rõ
3. Sound xuất hiện không đúng thời điểm (timing offset lỗi)
4. Giữa các sound không có gì "nối" — cảm giác rời rạc

---

## Architecture

```
[Timeline trống]
       │
       ▼
[Major placements]  ← Highlight score > 0.35 (hạ từ 0.5), LLM re-rank
       │
       ▼
[Minor placements]  ← 3 trigger: speech_pause + energy_dip + scene_change
       │
       ▼
[Gap-fill pass]     ← Quét gap > 8s → chèn minor filler tự động
       │
       ▼
[Background pass]   ← AI phân tích RMS → bật/tắt ambient music
       │
       ▼
[Merge & Render]    ← 3 volume riêng: major / minor / background
```

---

## Section 1: Tier Definitions

### Tier Major — Meme Punchline
- **Vai trò**: Emotional peak, punchline, reaction sound lớn
- **Trigger**: Highlight score > 0.35 (hạ từ 0.5)
- **Selection**: ChromaDB + LLM re-rank (giữ nguyên)
- **Volume**: `major_volume` slider (thay thế `meme_volume` cũ)
- **Timing fix**: Bỏ double-offset. Chỉ dùng `timing_type` offset, không cộng thêm `anticipation_ms`

### Tier Minor — Texture / Transition
- **Vai trò**: Rhythm, texture, lấp chỗ trống ngắn, báo hiệu transition
- **Trigger**: 3 loại:

| `cue_type` | Điều kiện | Sound phù hợp |
|---|---|---|
| `scene_change` | Frame diff > threshold (đã có) | Whoosh, swoosh |
| `speech_pause` | Im lặng trong transcript > 1500ms | Pop, ding nhẹ |
| `energy_dip` | RMS < 20% median, kéo dài > 1000ms | Ding, tick |

- **Selection**: Attention map (no LLM, giữ nguyên)
- **Volume**: `minor_volume` là slider độc lập (không derive từ `major_volume`). `MINOR_VOLUME_RATIO` bị xóa khỏi `placer.py`. Default UI = 0.35.
- **Gap giữa 2 minor**: tối thiểu 3000ms (giữ nguyên)

### Tier Background — Mood Glue *(NEW)*
- **Vai trò**: Ambient music nối giữa các sound chính, tạo không khí liên tục
- **Trigger logic**:
  1. Tính RMS trung bình theo từng segment 10s của audio gốc (dùng `extract_rms_segments(wav_path)` → `list[{start_ms, end_ms, rms_mean}]`)
  2. Segment nào `rms_mean < rms_threshold` → candidate. **`rms_threshold` mặc định = 0.02** (librosa RMS scale 0.0–1.0). Đây là constant trong `background_detector.py`, không phải UI config.
  3. Nếu tổng thời lượng candidate > 30% video → bật background
  4. Background fade in khi bắt đầu segment im, fade out tại `major_insert_ms - 1000ms`
- **Mood selection**: Dựa trên dominant emotion của highlights:
  - `shock/fail/awkward` → `dramatic`
  - `hype/funny` → `chill`
  - `sadness` → `chill`
  - fallback → `chill`
- **Volume**: `bg_volume` slider độc lập (recommended default: 0.15)

---

## Section 2: Gap-Fill Pass *(NEW)*

**Hàm**: `gap_fill_pass(placements: list[dict], total_duration_ms: int) -> list[dict]`
- **Input**: Danh sách merged placements (major + minor đã merge), không mutate in-place — trả về list mới
- **Output**: List placements gốc + các filler placement mới, đã sort theo `insert_ms`
- **Integration point trong `tasks.py`**: Gọi SAU `merge_placements()`, trước `create_background_placements()`

**Logic**:
```python
def gap_fill_pass(placements: list[dict], total_duration_ms: int) -> list[dict]:
    # Thêm sentinel đầu/cuối để xử lý gap đầu và cuối video
    sorted_p = sorted(placements, key=lambda p: p["insert_ms"])
    boundaries = [(0, sorted_p[0]["insert_ms"])] if sorted_p else [(0, total_duration_ms)]
    for i in range(len(sorted_p) - 1):
        boundaries.append((sorted_p[i]["end_ms"], sorted_p[i+1]["insert_ms"]))
    if sorted_p:
        boundaries.append((sorted_p[-1]["end_ms"], total_duration_ms))

    fillers = []
    for gap_start, gap_end in boundaries:
        gap_dur = gap_end - gap_start
        if gap_dur > 8000:
            num_fillers = gap_dur // 8000
            spacing = gap_dur // (num_fillers + 1)
            for j in range(1, num_fillers + 1):
                filler = pick_filler_sound()  # lấy từ attention pool, sound < 1000ms
                if filler:
                    fillers.append({**filler, "insert_ms": gap_start + spacing * j, "track": "filler"})

    return sorted(placements + fillers, key=lambda p: p["insert_ms"])
```

**Filler sound**: Lấy từ attention pool (tier=attention), ưu tiên `duration_ms < 1000ms` (whoosh, pop, ding). Không dùng LLM. Fillers được tính vào `minor_count` trong kết quả trả về. Nếu gap rất lớn, sẽ chèn nhiều filler (cách đều nhau).

**Mục đích**: Đảm bảo không có khoảng im lặng > 8s mà không có sound gì — giải quyết cảm giác "tách rời".

---

## Section 3: Timing Fix

**Vấn đề hiện tại**: `create_placements()` trong `placer.py` áp dụng cả `timing_type` offset lẫn `anticipation_ms = 200` → double-offset, sound nổi vào sớm hơn thực tế.

**Fix**: Xóa `anticipation_ms` parameter. Chỉ giữ `timing_type` offset:

```python
# Trước (lỗi)
insert_ms = calculate_insert_ms(...)
if timing_type in ("instant", "buildup"):
    insert_ms -= anticipation_ms  # double offset

# Sau (đúng)
insert_ms = calculate_insert_ms(...)
# Không cộng thêm gì nữa
```

---

## Section 4: SQLite Schema Update

Thêm `mood` column vào bảng `sounds`:

```sql
ALTER TABLE sounds ADD COLUMN mood TEXT;
-- mood values: 'chill' | 'dramatic' | 'hype' | 'ambient' | NULL
```

Update ingestion/tagger để auto-tag `mood` cho sound có `tier = 'background'`.

---

## Section 5: Backend Changes

### Hàm signatures mới

**`detection/minor_cues.py`** — 2 hàm mới, trả về `list[MinorCue]`:
```python
def extract_speech_pause_cues(
    segments: list[dict],          # output của parse_whisper_segments() — [{start, end, text}]
    min_pause_ms: int = 1500,
    major_highlights: list = None,
    major_buffer_ms: int = MAJOR_BUFFER_MS,
) -> list[MinorCue]:
    """Detect gaps > min_pause_ms between transcript segments."""

def extract_energy_dip_cues(
    rms_segments: list[dict],      # output của extract_rms_segments() — [{start_ms, end_ms, rms_mean}]
    min_dip_duration_ms: int = 1000,
    major_highlights: list = None,
    major_buffer_ms: int = MAJOR_BUFFER_MS,
) -> list[MinorCue]:
    """Detect RMS < 20% of video median, lasting > min_dip_duration_ms."""
```

**Merge trong `tasks.py`**:
```python
all_minor_cues = (
    extract_minor_cues(visual_events, major_highlights=highlights)     # scene_change
    + extract_speech_pause_cues(segments, major_highlights=highlights) # speech_pause
    + extract_energy_dip_cues(rms_segments, major_highlights=highlights) # energy_dip
)
all_minor_cues.sort(key=lambda c: c.timestamp_ms)
all_minor_cues = plan_minor_density(all_minor_cues, duration_sec, niche=niche)
```

**`signals/audio_signals.py`** — hàm mới:
```python
def extract_rms_segments(
    wav_path: str,
    segment_duration_s: float = 10.0,
) -> list[dict]:  # [{"start_ms": int, "end_ms": int, "rms_mean": float}]
```
Dùng librosa để load WAV, chia thành segments, tính RMS mean mỗi segment.

### Renderer — ffmpeg filter cho background track

Background track có cấu trúc khác với sound effects: nó là 1 file audio có thể ngắn hơn video, cần được loop (bằng cách thêm flag `-stream_loop -1` khi truyền input file), trim và fade động theo `bg_segments`.

**Thiết kế filter_complex**:
```
# bg_segments = list[{start_ms, end_ms}] — các đoạn cần phủ background
# Mỗi segment tạo 1 input stream (input này đã được mở với -stream_loop -1):
[N:a]atrim=start={start_s}:end={end_s},
    asetpts=PTS-STARTPTS,
    afade=t=in:st=0:d=0.5,
    afade=t=out:st={fade_out_offset}:d=1.0,
    adelay={start_ms}|{start_ms},
    apad=whole_dur={total_dur}[bg{i}]

# Các bg streams mix thành 1 bus với volume bg_volume:
[bg0][bg1]...amix=inputs={n}:normalize=0,volume={bg_volume}[bgall]

# bgall mix với sfxall và original:
[0:a][sfxall][bgall]amix=inputs=3:duration=first:normalize=0:weights=1 1 1,volume=3[aout]
```

`fade_out_offset` tính theo: `min(end_s - start_s - 1.0, end_s - start_s - 0.1)` (lưu ý tính dựa trên thời gian sau khi atrim và asetpts, nên nó là duration của segment). Hoặc nếu có major sound ngay sau: khoảng cách từ đầu segment tới lúc fade out.

**Hàm mới trong `renderer.py`**:
```python
def build_background_filter_parts(
    bg_placements: list[dict],  # [{sound_file, start_ms, end_ms, volume}]
    total_duration_s: float,
    start_input_idx: int,       # index sau tất cả SFX inputs
) -> tuple[list[str], list[str], str]:
    """Returns (inputs, filter_parts, '[bgall]' label)"""
```

### File table

| File | Thay đổi |
|---|---|
| `detection/highlight_detector.py` | Hạ threshold `0.5 → 0.35` |
| `detection/minor_cues.py` | Thêm `extract_speech_pause_cues()` và `extract_energy_dip_cues()` |
| `signals/audio_signals.py` | Thêm `extract_rms_segments()` |
| `detection/background_detector.py` | **[NEW]** `should_use_background()`, `select_background_mood()`, `get_background_segments()` |
| `sound/attention_map.py` | Thêm mapping `speech_pause` → `["pop", "ding"]`, `energy_dip` → `["ding", "tick"]` |
| `placement/placer.py` | Xóa `anticipation_ms` và `MINOR_VOLUME_RATIO`, thêm `gap_fill_pass()`, thêm `create_background_placements()` |
| `render/renderer.py` | Thêm `build_background_filter_parts()`, update `build_ffmpeg_filter()` nhận bg bus |
| `tasks.py` | Nhận `minor_volume`, `bg_volume`; merge 3 cue sources; gọi background pipeline |

---

## Section 6: Frontend Changes

| File | Thay đổi |
|---|---|
| `frontend/index.html` | Thay 1 slider `memeVolumeSlider` → 3 slider: Major / Minor / Background |
| `frontend/app.js` | Gửi `major_volume`, `minor_volume`, `bg_volume` thay vì `meme_volume`. `getMemeVolume()` → `getMajorVolume()` |
| `frontend/style.css` | Style 3 slider group, label rõ ràng |

**UI layout cho 3 slider:**
```
🔊 Sound chính (meme)    [========●--] 70%
🔉 Hiệu ứng phụ          [=====●-----] 35%
🎵 Nhạc nền              [==●--------] 15%
```

---

## Section 7: Verification Plan

### Automated
- `gap_fill_pass()`: assert không có gap > 8000ms sau khi fill; test boundary gap = 8000ms (strictly greater → không fill), gap = 8001ms (fill)
- `gap_fill_pass()`: assert filler placement không overlap major sound (integration)
- `extract_speech_pause_cues()`: assert pause > 1500ms detected; pause ≤ 1500ms không detect
- `extract_energy_dip_cues()`: assert dip < 20% median, > 1000ms detected
- `should_use_background()`: test video RMS cao (< 30% silent → tắt); test video RMS thấp (≥ 30% silent → bật)
- `select_background_mood()`: assert emotion `shock` → `dramatic`, fallback → `chill`
- `build_background_filter_parts()`: assert filter string hợp lệ với n=1 và n=3 segments

### Manual
- Upload video 2 phút im lặng nhiều → background bật, minor dày, ≥ 8 sound total
- Upload video 2 phút ồn ào (nhạc gốc to) → background tắt
- Timing check: sound chính nổi đúng moment (không double-offset)
- Gap check: không có khoảng im > 8s trong output

---

## Section 8: Data Migration

Thêm `mood` column:
```sql
ALTER TABLE sounds ADD COLUMN mood TEXT;
```

**Backfill existing rows**: Thêm script `scripts/backfill_mood.py` (tương tự `scripts/backfill_tiers.py` đã có):
- Với mỗi sound có `tier = 'background'` và `mood IS NULL` → gọi LLM tagger để assign mood
- Với sound không phải background → mood giữ NULL (không dùng)

---

## Open Questions (Resolved)
- ✅ Approach: B — 3-Layer Cohesive Audio
- ✅ Density: Adaptive — dày khi im, thưa khi ồn
- ✅ Background: AI tự quyết dựa trên RMS + mood
- ✅ Volume: 3 slider độc lập trên UI, `MINOR_VOLUME_RATIO` bị xóa
- ✅ Gap threshold: > 8000ms (strictly greater)
- ✅ Speech pause threshold: 1500ms
- ✅ Background activate threshold: ≥ 30% video im ắng (rms < 0.02)
- ✅ `rms_threshold`: constant 0.02 trong `background_detector.py`
- ✅ Minor volume: slider độc lập, default 0.35, không derive từ major
