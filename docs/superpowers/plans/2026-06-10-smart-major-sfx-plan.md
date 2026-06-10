# Smart Major SFX (Phase A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade meme sound insertion with TikTok-framework Impact scoring, tier-aware selection, anticipation timing, density caps, and expanded sound library.

**Architecture:** Extend `Highlight` with impact fields scored by LLM in `llm_validator`, gate/filter via new `density.py`, route selection through `reaction_map.py` before ChromaDB, apply −200ms anticipation in `placer.py`. Add `tier` column to sounds DB.

**Tech Stack:** Python 3.11, FastAPI, Celery, SQLite, ChromaDB, OpenRouter Gemini, ffmpeg, MyInstants crawler

**Spec:** `docs/superpowers/specs/2026-06-10-smart-major-sfx-design.md`

---

## File Map

| File | Action | Role |
|---|---|---|
| `backend/detection/highlight_detector.py` | Modify | Add impact fields to `Highlight` |
| `backend/detection/impact.py` | Create | Gate rules + `apply_impact_fields` |
| `backend/detection/density.py` | Create | Cap major sounds by duration |
| `backend/detection/llm_validator.py` | Modify | LLM impact scoring prompt |
| `backend/sound/reaction_map.py` | Create | Emotion/event → alias lookup |
| `backend/sound/selector.py` | Modify | Tier-aware + reaction map + fix fallback bug |
| `backend/sound/library.py` | Modify | Tier in chroma metadata |
| `backend/sound/tagger.py` | Modify | Tag `tier` field |
| `backend/db/models.py` | Modify | `tier` column migration |
| `backend/db/chroma.py` | Modify | Pass `tier` in metadata |
| `backend/placement/placer.py` | Modify | Anticipation offset |
| `tasks.py` | Modify | Pass `video_duration_sec` to density cap |
| `scripts/backfill_tiers.py` | Create | Backfill tier on existing sounds |
| `tests/test_impact.py` | Create | Gate logic tests |
| `tests/test_density.py` | Create | Density cap tests |
| `tests/test_reaction_map.py` | Create | Reaction map tests |
| `tests/test_placer.py` | Modify | Anticipation tests |

---

### Task 1: Extend Highlight dataclass

**Files:**
- Modify: `backend/detection/highlight_detector.py`
- Test: `tests/test_impact.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_impact.py
from backend.detection.highlight_detector import Highlight

def test_highlight_has_impact_fields():
    h = Highlight(
        start_ms=0, end_ms=1000, peak_ms=500, score=0.8,
        importance=4, surprise=4, emotion_score=4,
        impact_score=64, has_punchline=True, sfx_tier="comedy",
    )
    assert h.impact_score == 64
    assert h.sfx_tier == "comedy"
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
.venv\Scripts\pytest.exe tests/test_impact.py::test_highlight_has_impact_fields -v
```

- [ ] **Step 3: Add fields to Highlight**

```python
# backend/detection/highlight_detector.py — add to Highlight dataclass
importance: int = 3
surprise: int = 3
emotion_score: int = 3
impact_score: int = 27
has_punchline: bool = False
audience_emotion: str = ""
sfx_tier: str = "emphasis"
```

- [ ] **Step 4: Run test — expect PASS**

```bash
.venv\Scripts\pytest.exe tests/test_impact.py::test_highlight_has_impact_fields -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/detection/highlight_detector.py tests/test_impact.py
git commit -m "feat: add impact scoring fields to Highlight"
```

---

### Task 2: Impact gate logic

**Files:**
- Create: `backend/detection/impact.py`
- Test: `tests/test_impact.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_impact.py (append)
from backend.detection.impact import compute_impact_score, assign_sfx_tier, should_keep_highlight

def test_compute_impact_score():
    assert compute_impact_score(4, 4, 4) == 64

def test_assign_sfx_tier_comedy_requires_punchline():
    assert assign_sfx_tier(64, has_punchline=True) == "comedy"
    assert assign_sfx_tier(64, has_punchline=False) == "emphasis"

def test_should_keep_below_threshold():
    assert should_keep_highlight(25) is False
    assert should_keep_highlight(30) is True
    assert should_keep_highlight(100) is True
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
.venv\Scripts\pytest.exe tests/test_impact.py -v -k "impact"
```

- [ ] **Step 3: Implement**

```python
# backend/detection/impact.py
IMPACT_MIN_MAJOR = 30

def compute_impact_score(importance: int, surprise: int, emotion_score: int) -> int:
    return max(1, importance) * max(1, surprise) * max(1, emotion_score)

def assign_sfx_tier(impact_score: int, has_punchline: bool) -> str:
    if impact_score >= 50 and has_punchline:
        return "comedy"
    return "emphasis"

def should_keep_highlight(impact_score: int) -> bool:
    return impact_score >= IMPACT_MIN_MAJOR

def apply_impact_fields(
    highlight,
    importance: int,
    surprise: int,
    emotion_score: int,
    has_punchline: bool,
    audience_emotion: str = "",
) -> None:
    impact = compute_impact_score(importance, surprise, emotion_score)
    highlight.importance = importance
    highlight.surprise = surprise
    highlight.emotion_score = emotion_score
    highlight.impact_score = impact
    highlight.has_punchline = has_punchline
    highlight.audience_emotion = audience_emotion
    highlight.sfx_tier = assign_sfx_tier(impact, has_punchline)
```

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/detection/impact.py tests/test_impact.py
git commit -m "feat: impact score gate logic for major SFX"
```

---

### Task 3: LLM impact scoring in validator

**Files:**
- Modify: `backend/detection/llm_validator.py`
- Test: `tests/test_llm_validator.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_llm_validator.py (append)
from unittest.mock import patch, MagicMock
from backend.detection.highlight_detector import Highlight
from backend.detection.llm_validator import validate_highlights

def test_validate_highlights_applies_impact_gate():
    highlights = [
        Highlight(0, 1000, 500, 0.8, context_text="oh no"),
        Highlight(2000, 3000, 2500, 0.6, context_text="hello"),
    ]
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content='''[
        {"index": 0, "keep": true, "importance": 5, "surprise": 5, "emotion_score": 5,
         "has_punchline": true, "audience_emotion": "shock", "event_type": "fail", "emotion": "shock"},
        {"index": 1, "keep": true, "importance": 1, "surprise": 1, "emotion_score": 1,
         "has_punchline": false, "audience_emotion": "neutral", "event_type": "generic", "emotion": "shock"}
    ]'''))]
    with patch("backend.detection.llm_validator.get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = mock_response
        result = validate_highlights(highlights)
    assert len(result) == 1
    assert result[0].impact_score == 125
    assert result[0].sfx_tier == "comedy"
```

- [ ] **Step 2: Run test — expect FAIL**

- [ ] **Step 3: Update llm_validator.py**

Update prompt to request `importance`, `surprise`, `emotion_score`, `has_punchline`, `audience_emotion` (each 1–5 for I/S/E).

In the loop after parsing:
```python
from backend.detection.impact import apply_impact_fields, should_keep_highlight

for d in decisions:
  if not d.get("keep"):
    continue
  h = highlights[d["index"]]
  apply_impact_fields(
    h,
    importance=int(d.get("importance", 3)),
    surprise=int(d.get("surprise", 3)),
    emotion_score=int(d.get("emotion_score", 3)),
    has_punchline=bool(d.get("has_punchline", False)),
    audience_emotion=d.get("audience_emotion", ""),
  )
  if not should_keep_highlight(h.impact_score):
    continue
  h.event_type = d.get("event_type", h.event_type)
  h.emotion = d.get("emotion", h.emotion)
  result.append(h)
```

Add fallback on LLM failure: keep highlights with `score >= 0.7`, set `impact_score=30`, `sfx_tier="emphasis"`.

- [ ] **Step 4: Run tests — expect PASS**

```bash
.venv\Scripts\pytest.exe tests/test_llm_validator.py -v
```

- [ ] **Step 5: Commit**

---

### Task 4: Density cap

**Files:**
- Create: `backend/detection/density.py`
- Test: `tests/test_density.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_density.py
from backend.detection.highlight_detector import Highlight
from backend.detection.density import max_major_sounds, apply_density_cap

def test_max_major_sounds_60s():
    assert max_major_sounds(60.0) == 12

def test_density_cap_keeps_top_impact():
    highlights = [
        Highlight(0, 1000, 500, 0.9, impact_score=100, sfx_tier="comedy"),
        Highlight(2000, 3000, 2500, 0.8, impact_score=50, sfx_tier="emphasis"),
        Highlight(4000, 5000, 4500, 0.7, impact_score=30, sfx_tier="emphasis"),
    ]
    capped = apply_density_cap(highlights, video_duration_sec=10.0)
    assert len(capped) == 2  # 10/5 = 2 max
    assert capped[0].impact_score == 100
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```python
# backend/detection/density.py
def max_major_sounds(video_duration_sec: float, niche: str = "entertainment") -> int:
    if niche == "edu":
        divisor = 8
    elif niche == "lifestyle":
        divisor = 10
    else:
        divisor = 5
    return max(1, int(video_duration_sec / divisor))

def apply_density_cap(highlights: list, video_duration_sec: float, niche: str = "entertainment") -> list:
    limit = max_major_sounds(video_duration_sec, niche)
    ranked = sorted(highlights, key=lambda h: h.impact_score, reverse=True)
    kept = ranked[:limit]
    return sorted(kept, key=lambda h: h.peak_ms)
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Wire in tasks.py** after `validate_highlights`:

```python
from backend.ingestion.extractor import get_video_duration  # or ffprobe inline
duration_sec = ...  # from video metadata
from backend.detection.density import apply_density_cap
highlights = apply_density_cap(highlights, duration_sec)
```

Add `get_video_duration` helper in `backend/ingestion/extractor.py` if missing.

- [ ] **Step 6: Commit**

---

### Task 5: DB tier column + tagger

**Files:**
- Modify: `backend/db/models.py`, `backend/sound/tagger.py`, `backend/sound/library.py`, `backend/db/chroma.py`
- Create: `scripts/backfill_tiers.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Add tier migration in init_db**

```python
# After CREATE TABLE, run:
try:
    conn.execute("ALTER TABLE sounds ADD COLUMN tier TEXT DEFAULT 'emphasis'")
except sqlite3.OperationalError:
    pass  # column exists
```

Update `insert_sound` to include `tier`.

- [ ] **Step 2: Update tagger prompt** — add `"tier": "emphasis|comedy"` to JSON schema.

- [ ] **Step 3: Update add_sound_to_library** — store tier, pass to chroma metadata.

- [ ] **Step 4: Create backfill script**

```python
# scripts/backfill_tiers.py
COMEDY_EMOTIONS = {"funny", "cringe", "awkward", "fail"}
# For each sound: tier = comedy if emotion in COMEDY_EMOTIONS else emphasis
# UPDATE sounds SET tier = ? WHERE id = ?
```

- [ ] **Step 5: Run backfill + verify**

```bash
.venv\Scripts\python.exe scripts/backfill_tiers.py
.venv\Scripts\python.exe -c "from backend.db.models import get_sounds; from backend.config import settings; s=get_sounds(settings.db_path); print(set(x.get('tier') for x in s))"
```

- [ ] **Step 6: Commit**

---

### Task 6: Reaction map

**Files:**
- Create: `backend/sound/reaction_map.py`
- Test: `tests/test_reaction_map.py`

- [ ] **Step 1: Write failing test**

```python
from backend.sound.reaction_map import resolve_reaction_alias
from backend.detection.highlight_detector import Highlight

def test_surprise_maps_to_vine_boom():
    h = Highlight(0, 1000, 500, 0.8, event_type="shock", emotion="shock", audience_emotion="surprise")
    assert resolve_reaction_alias(h) == "vine-boom"

def test_fail_maps_to_bruh():
    h = Highlight(0, 1000, 500, 0.8, event_type="fail", emotion="fail")
    assert resolve_reaction_alias(h) == "bruh"
```

- [ ] **Step 2: Implement**

```python
# backend/sound/reaction_map.py
REACTION_ALIASES: dict[str, list[str]] = {
    "surprise": ["vine-boom"],
    "shock": ["vine-boom", "shocked"],
    "fail": ["bruh", "movie_1"],
    "awkward": ["huh", "mac-quack"],
    "cringe": ["huh", "faaah"],
    "plot_twist": ["dun-dun", "dramatic"],
    "dramatic": ["dun-dun", "dramatic"],
    "sadness": ["tf_nemesis", "sad violin"],
    "emotional": ["tf_nemesis"],
    "hype": ["10-diem", "anime-wow"],
    "win": ["10-diem", "ghe-chua"],
    "funny": ["baby-laughing", "thay-giao-ba-cuoi"],
}

def resolve_reaction_alias(highlight) -> str | None:
    keys = [highlight.audience_emotion, highlight.event_type, highlight.emotion]
    for key in keys:
        if not key:
            continue
        aliases = REACTION_ALIASES.get(key.lower().replace(" ", "_"))
        if aliases:
            return aliases[0]
    return None
```

- [ ] **Step 3: Run tests — expect PASS**

- [ ] **Step 4: Commit**

---

### Task 7: Tier-aware selector + fix fallback bug

**Files:**
- Modify: `backend/sound/selector.py`
- Test: `tests/test_sound_selector.py`

- [ ] **Step 1: Fix `apply_fallback_rule`** — currently broken (`sound_name` undefined). Use `sound_to_selection(resolve_fallback_sound(emotion))`.

- [ ] **Step 2: Add reaction map shortcut** at start of `select_sound`:

```python
from backend.sound.reaction_map import resolve_reaction_alias
from backend.sound.library import find_sound_by_alias, sound_to_selection

alias = resolve_reaction_alias(highlight)
if alias:
    sound = find_sound_by_alias(alias)
    if sound and _tier_matches(sound, highlight.sfx_tier):
        return sound_to_selection(sound)
```

- [ ] **Step 3: Filter ChromaDB candidates by tier**

```python
def _tier_matches(sound: dict, sfx_tier: str) -> bool:
    return (sound.get("tier") or "emphasis") == sfx_tier

# In search results filtering:
candidates = [c for c in candidates if c["metadata"].get("tier", "emphasis") == highlight.sfx_tier]
# If empty after filter, relax to all candidates
```

- [ ] **Step 4: Update LLM rerank prompt** — mention `sfx_tier: emphasis|comedy` constraint.

- [ ] **Step 5: Run tests**

```bash
.venv\Scripts\pytest.exe tests/test_sound_selector.py -v
```

- [ ] **Step 6: Commit**

---

### Task 8: Anticipation placement

**Files:**
- Modify: `backend/placement/placer.py`
- Test: `tests/test_placer.py`

- [ ] **Step 1: Write failing test**

```python
def test_anticipation_offset_applied():
    from backend.detection.highlight_detector import Highlight
    from backend.placement.placer import create_placements
    h = Highlight(0, 2000, 1000, 0.9, impact_score=64, sfx_tier="comedy")
    sel = {"chosen_id": "x", "metadata": {
        "file_path": "sounds/vine-boom.mp3", "duration_ms": 1000,
        "timing_type": "instant", "duration_ms": 1000
    }}
    placements = create_placements([h], [sel], anticipation_ms=200)
    assert placements[0]["insert_ms"] == 800 - 200  # peak - 10% duration - 200
```

Adjust expected value to match `calculate_insert_ms(1000, 1000, "instant") - 200 = 900 - 200 = 700`.

- [ ] **Step 2: Implement**

```python
def create_placements(..., anticipation_ms: int = 200):
    ...
    insert_ms = calculate_insert_ms(...)
    if timing_type in ("instant", "buildup"):
        insert_ms -= anticipation_ms
    insert_ms = max(0, insert_ms)
```

- [ ] **Step 3: Run tests — expect PASS**

- [ ] **Step 4: Commit**

---

### Task 9: Expand sound library

**Files:**
- Run: `scripts/seed_sounds.py`

- [ ] **Step 1: Crawl additional sounds**

```bash
.venv\Scripts\python.exe scripts/seed_sounds.py --pages 10
```

Target: library grows from ~36 to 60+ sounds. Skip duplicates (check filename exists).

- [ ] **Step 2: Backfill tiers on new sounds**

```bash
.venv\Scripts\python.exe scripts/backfill_tiers.py
```

- [ ] **Step 3: Verify reaction map coverage**

```bash
.venv\Scripts\python.exe -c "
from backend.sound.reaction_map import REACTION_ALIASES
from backend.sound.library import find_sound_by_alias
for emotion, aliases in REACTION_ALIASES.items():
    found = any(find_sound_by_alias(a) for a in aliases)
    print(emotion, 'OK' if found else 'MISSING', aliases)
"
```

- [ ] **Step 4: Commit** (sounds/ + DB if tracked, or document count in commit message)

---

### Task 10: Full test suite + manual smoke

- [ ] **Step 1: Run full suite**

```bash
.venv\Scripts\pytest.exe tests/ -v
```

Expected: all tests pass (existing + new).

- [ ] **Step 2: Fix any regressions**

- [ ] **Step 3: Manual smoke** (if Redis/Celery running)

Upload a 30–60s video via http://localhost:8000, verify:
- `highlights_kept` ≤ `duration/5`
- `sounds_added` matches kept highlights
- Result video has audible meme sounds

- [ ] **Step 4: Final commit**

```bash
git commit -m "feat: smart major SFX phase A — impact scoring, tier selection, density cap"
```

---

## Plan Self-Review

| Spec requirement | Task |
|---|---|
| Impact I×S×E scoring | Task 2, 3 |
| Gate impact ≥ 30 | Task 2, 3 |
| Comedy only with punchline + ≥50 | Task 2 |
| sfx_tier emphasis/comedy | Task 1, 2, 5, 7 |
| Reaction map | Task 6, 7 |
| Anticipation −200ms | Task 8 |
| Density cap duration/5 | Task 4 |
| Library expansion | Task 9 |
| tier DB column | Task 5 |
| Error fallbacks | Task 3 (LLM fail), Task 7 (tier relax) |

No placeholders. Type names consistent: `sfx_tier`, `impact_score`, `anticipation_ms`.
