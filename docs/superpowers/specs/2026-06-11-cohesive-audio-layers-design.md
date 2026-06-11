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
- **Volume**: `minor_volume` slider (fixed ratio ~35% so với major nếu không set)
- **Gap giữa 2 minor**: tối thiểu 3000ms (giữ nguyên)

### Tier Background — Mood Glue *(NEW)*
- **Vai trò**: Ambient music nối giữa các sound chính, tạo không khí liên tục
- **Trigger logic**:
  1. Tính RMS trung bình theo từng segment 10s của audio gốc
  2. Segment nào RMS < `rms_threshold` (im ắng) → candidate
  3. Nếu tổng thời lượng candidate > 30% video → bật background
  4. Background fade in khi bắt đầu segment im, fade out 1s trước major sound
- **Mood selection**: Dựa trên dominant emotion của highlights:
  - `shock/fail/awkward` → dramatic
  - `hype/funny` → upbeat/chill
  - `sadness` → lo-fi/soft
- **Volume**: `bg_volume` slider (recommended default: 0.15)

---

## Section 2: Gap-Fill Pass *(NEW)*

Sau khi merge major + minor placements, quét toàn bộ timeline:

```
for mỗi gap giữa 2 placement liên tiếp:
    if gap_duration > 8000ms:
        chèn 1 minor filler tại midpoint của gap
```

**Filler sound**: Lấy từ attention pool (tier=attention), ưu tiên sound ngắn < 1000ms (whoosh, pop, ding). Không dùng LLM. Max 1 filler per gap.

**Mục đích**: Đảm bảo không có khoảng im lặng quá dài (>8s) mà không có sound gì — giải quyết cảm giác "tách rời".

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

| File | Thay đổi |
|---|---|
| `detection/highlight_detector.py` | Hạ threshold `0.5 → 0.35` |
| `detection/minor_cues.py` | Thêm `extract_speech_pause_cues()` và `extract_energy_dip_cues()` |
| `signals/audio_signals.py` | Thêm `extract_rms_segments()` → trả về list `{start_ms, end_ms, rms}` |
| `detection/background_detector.py` | **[NEW]** `should_use_background(rms_segments, threshold)` + `select_background_mood(highlights)` |
| `sound/attention_map.py` | Thêm mapping `speech_pause` → `["pop", "ding"]`, `energy_dip` → `["ding", "tick"]` |
| `placement/placer.py` | Xóa `anticipation_ms`, thêm `gap_fill_pass()`, thêm `create_background_placements()` |
| `render/renderer.py` | Support background track với fade in/out riêng |
| `tasks.py` | Nhận `minor_volume`, `bg_volume`; gọi background pipeline |

---

## Section 6: Frontend Changes

| File | Thay đổi |
|---|---|
| `frontend/index.html` | Thay 1 slider `memeVolumeSlider` → 3 slider: Major / Minor / Background |
| `frontend/app.js` | Gửi `major_volume`, `minor_volume`, `bg_volume` thay vì `meme_volume` |
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
- Unit test `gap_fill_pass()`: assert không có gap > 8s sau khi fill
- Unit test `extract_speech_pause_cues()`: assert pause > 1500ms được detect
- Unit test `should_use_background()`: test với RMS cao (silent ít) và RMS thấp (silent nhiều)

### Manual
- Upload video 2 phút im lặng nhiều → expect background bật + minor dày hơn
- Upload video 2 phút ồn ào (nhạc gốc to) → expect background tắt
- Kiểm tra timing: sound chính phải nổi đúng moment, không sớm/muộn

---

## Open Questions (Resolved)
- ✅ Approach: B — 3-Layer Cohesive Audio
- ✅ Density: Adaptive — dày khi im, thưa khi ồn
- ✅ Background: AI tự quyết dựa trên RMS + mood
- ✅ Volume: 3 slider riêng trên UI
- ✅ Gap threshold: 8s
- ✅ Speech pause threshold: 1500ms
- ✅ Background activate threshold: > 30% video im ắng
