# Smart Major SFX — Phase A Design

**Date:** 2026-06-10  
**Status:** Approved by user  
**Source framework:** `tiktok-sfx-framework.md`  
**Roadmap:** Phase A (this spec) → Phase B (Dual-Track minor SFX)

---

## 1. Overview

Nâng cấp pipeline chèn meme sound từ “gặp signal là chèn” sang **editor-grade Major SFX logic** dựa trên TikTok SFX Framework:

```
Impact = Importance × Surprise × Emotion   (mỗi thang 1–5)
```

Phase A chỉ xử lý **Major meme sounds** (Tier 2 Emphasis + Tier 3 Comedy). Tier 1 Attention (whoosh/pop/click) được defer sang Phase B.

User đã approve: **A trước, B sau**, và **có thể tải thêm meme sounds** từ MyInstants.

---

## 2. Goals & Non-Goals

### Goals
- Chấm Impact score (I×S×E) cho mỗi highlight qua LLM
- Gate: chỉ chèn khi impact đủ ngưỡng (≥ 30 emphasis, ≥ 50 + punchline cho comedy)
- Gán `tier` (`emphasis` | `comedy`) cho sound library
- Reaction map: emotion/event → sound ưu tiên trước ChromaDB
- Anticipation timing: sound xuất hiện **200ms trước** đỉnh cảm xúc
- Density cap: tối đa `duration_sec / 5` major sounds (niche entertainment)
- Mở rộng library: crawl thêm meme sounds từ MyInstants

### Non-Goals (Phase B)
- Minor SFX track (whoosh, pop, click)
- Density planner 1 Major + 2–5 Minor / 10s
- Zoom + sound combo detection
- Niche selector trên UI (hardcode `entertainment` trong Phase A)

---

## 3. Architecture

```
Signals → detect_highlights (score 0–1)
              ↓
        llm_validator (impact scoring + gate + enrich)
              ↓
        density_cap (top-N by impact_score)
              ↓
        selector (reaction map → ChromaDB → LLM rerank, tier-aware)
              ↓
        placer (anticipation −200ms + overlap resolve)
              ↓
        renderer (ffmpeg mix)
```

### New / Modified Units

| Unit | Responsibility |
|---|---|
| `Highlight` dataclass | Thêm `importance`, `surprise`, `emotion_score`, `impact_score`, `has_punchline`, `audience_emotion`, `sfx_tier` |
| `llm_validator.py` | Chấm I/S/E, gate keep/skip, set `sfx_tier` |
| `density.py` (new) | Cap major sounds theo video duration |
| `reaction_map.py` (new) | Hardcoded emotion/event → sound alias |
| `library.py` + DB | Field `tier: emphasis\|comedy` |
| `selector.py` | Tier filter + reaction map shortcut |
| `placer.py` | `anticipation_ms` offset |
| `tagger.py` | Tag `tier` khi seed sound mới |
| `scripts/seed_sounds.py` | Crawl thêm pages |

---

## 4. Impact Scoring & Gate Rules

LLM nhận highlight + transcript context, trả về per-highlight:

```json
{
  "index": 0,
  "keep": true,
  "importance": 4,
  "surprise": 4,
  "emotion_score": 4,
  "has_punchline": true,
  "audience_emotion": "curiosity",
  "event_type": "plot_twist",
  "emotion": "shock"
}
```

**Derived fields (code, không LLM):**
- `impact_score = importance × surprise × emotion_score`
- `sfx_tier` assignment:

| impact_score | has_punchline | sfx_tier | keep |
|---|---|---|---|
| < 30 | — | — | false |
| 30–49 | — | `emphasis` | true |
| ≥ 50 | false | `emphasis` | true |
| ≥ 50 | true | `comedy` | true |

Moments impact 10–29 bị loại (Phase B sẽ dùng cho Tier 1 minor).

---

## 5. Reaction Map (Tier 2–3 shortcuts)

Trước ChromaDB search, thử match reaction map:

| audience_emotion / event_type | Tier | Sound alias |
|---|---|---|
| surprise, shock | emphasis | vine-boom |
| fail | comedy | bruh |
| awkward, cringe | comedy | huh, mac-quack |
| plot_twist, dramatic | emphasis | dun-dun, dramatic |
| sadness, emotional | comedy | sad-violin (tf_nemesis) |
| hype, win | emphasis | 10-diem, anime-wow |
| funny | comedy | baby-laughing, thay-giao-ba-cuoi |

Nếu alias resolve được trong DB → dùng luôn, skip LLM rerank. Nếu không → fallback ChromaDB pipeline hiện tại, filter candidates theo `sfx_tier`.

---

## 6. Timeline Placement

### Anticipation offset
Framework: *sound xuất hiện trước đỉnh cảm xúc 100–300ms*.

Phase A default: **`anticipation_ms = 200`**

```
insert_ms = calculate_insert_ms(...) - anticipation_ms
insert_ms = max(0, insert_ms)
```

Áp dụng cho `timing_type` = `instant` và `buildup`. `reaction` giữ `end_ms + 200` (sound sau moment).

### Density cap
```python
max_major = max(1, int(video_duration_sec / 5))  # entertainment niche
```
Sau impact gate, sort by `impact_score` desc, giữ top `max_major`.

Video 30s → max 6 major. Video 60s → max 12. Video 180s → max 36.

---

## 7. Sound Library Expansion

### DB schema addition
```sql
ALTER TABLE sounds ADD COLUMN tier TEXT DEFAULT 'emphasis';
-- values: 'emphasis' | 'comedy'
```

### Tagging
`tagger.py` prompt thêm field `tier: emphasis|comedy`.

### Backfill
Script `scripts/backfill_tiers.py`: infer tier từ emotion hiện có:
- `funny|cringe|awkward|fail` → comedy
- còn lại → emphasis

### Crawl more sounds
```bash
python scripts/seed_sounds.py --pages 10
```
Target: 60–80 meme sounds covering reaction map gaps (bruh, cricket equivalent, bonk if available).

ChromaDB metadata thêm `tier` cho filter search.

---

## 8. Data Flow Example

Video 45s, entertainment:

1. Raw highlights detected: 8 moments
2. LLM impact scoring: 5 pass gate (impact ≥ 30)
3. Density cap: `45/5 = 9` → giữ cả 5
4. Selector: moment #1 surprise → vine-boom (reaction map), moment #2 fail → bruh (ChromaDB comedy tier)
5. Placer: peak 4100ms → insert 3900ms (anticipation −200ms)
6. Render: 5 major meme sounds mixed at user `meme_volume`

---

## 9. Error Handling

| Case | Behavior |
|---|---|
| LLM impact scoring fails | Fallback: giữ highlights có `score ≥ 0.7`, `sfx_tier = emphasis` |
| Reaction map alias not in DB | Fall through to ChromaDB |
| No candidates after tier filter | `resolve_fallback_sound(emotion)` với tier constraint |
| Empty placements after gate | Render video copy (no SFX) — existing behavior |

---

## 10. Testing

- Unit: impact gate logic, density cap, anticipation offset, reaction map resolve
- Unit: tier backfill inference
- Integration: mock LLM → pipeline produces ≤ max_major placements
- Manual: upload 30s video, verify ≤ 6 sounds, comedy only on punchline moments

---

## 11. Phase B Preview (out of scope)

- Tier 1 sound library (whoosh, pop, click, swipe)
- Minor SFX track on scene cuts / transitions
- Density planner: enforce 1 Major + 2–5 Minor per 10s window
- UI niche selector (entertainment / edu / lifestyle)

---

## 12. Success Criteria

- [ ] Không chèn sound khi impact < 30
- [ ] Comedy tier chỉ khi impact ≥ 50 AND has_punchline
- [ ] ≤ `duration/5` major sounds per video
- [ ] Insert timing anticipation −200ms trước peak
- [ ] Library ≥ 60 sounds với tier tagged
- [ ] All existing tests pass + new unit tests for gate/density/placement
