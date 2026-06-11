# Meme Sound Auto-Inserter — Design Spec
**Date**: 2026-06-08  
**Author**: AI Design Session  
**Status**: Approved by user

---

## Overview

Hệ thống tự động chèn meme sound effects vào video short-form (< 3 phút) tại các thời điểm phù hợp. User upload video qua web app, hệ thống phân tích và trả về video đã chèn sound.

**Target users**: Content creators làm TikTok, Reels, Shorts  
**Platform**: Web app (upload → process → download)  
**Models**: OpenRouter (Gemini Flash, Whisper)  
**Sound source**: MyInstants.com/en/index/vn/

---

## Architecture Overview

**Approach**: Signal Pipeline + LLM Reasoning (Hybrid)

```
[Browser Upload]
      │
      ▼
[FastAPI Backend]  →  [Celery + Redis Queue]
                              │
                    ┌─────────┼─────────┐
                    ▼         ▼         ▼
              [Whisper]  [librosa]  [mediapipe]
              transcript  audio     face/scene
                    │         │         │
                    └─────────┼─────────┘
                              ▼
                   [Highlight Detection]
                    signal aggregation
                    + LLM validation
                              │
                              ▼
                   [Sound Selection]
                    ChromaDB search
                    + LLM re-rank
                              │
                              ▼
                   [Timeline Placement]
                    offset calculation
                    + overlap resolution
                              │
                              ▼
                   [ffmpeg Render]
                    audio mix + export
                              │
                              ▼
                   [Download Link]
```

---

## Section 1: Problem Decomposition

### Pipeline Steps

1. **Ingestion**
   - Validate format (mp4, mov, webm)
   - Extract audio track (WAV mono 16kHz)
   - Extract frames (1-2 fps)
   - Extract metadata (duration, resolution, fps)

2. **Signal Extraction** (parallel)
   - **Transcript**: Whisper via OpenRouter → text segments với timestamps
   - **Audio signals**: librosa → RMS peaks, silence detection, energy spikes
   - **Visual signals**: frame diff → scene changes
   - **Face signals**: mediapipe → expression per frame

3. **Highlight Detection**
   - Aggregate signals theo timeline
   - Score từng khoảnh khắc (0.0–1.0)
   - Filter score > 0.5
   - LLM validation pass
   - Output: `List<Highlight>`

4. **Sound Selection**
   - Embedding search ChromaDB → top-5 candidates
   - LLM re-rank → chọn 1 sound
   - Output: `List<{Highlight, Sound}>`

5. **Timeline Placement**
   - Tính exact insert timestamp theo `timing_type`
   - Resolve overlaps
   - Output: `List<Placement>`

6. **Audio Mixing + Render**
   - ffmpeg: mix original + sound effects
   - Normalize volume
   - Export MP4

---

## Section 2: Tech Stack (MVP)

| Layer | Tool | Version |
|---|---|---|
| Frontend | HTML + Vanilla JS | - |
| Backend | FastAPI | 0.110+ |
| Task Queue | Celery + Redis | - |
| Video processing | ffmpeg + moviepy | - |
| ASR | Whisper via OpenRouter | - |
| LLM | Gemini Flash via OpenRouter | gemini-2.0-flash |
| Audio analysis | librosa | 0.10+ |
| Face detection | mediapipe | 0.10+ |
| Vector DB | ChromaDB | 0.4+ |
| Metadata DB | SQLite | - |
| Sound crawler | requests + BeautifulSoup | - |
| Deploy | Railway / Render | - |

### Cost per Video (< 3 min)
- Whisper: ~$0.009
- Gemini Flash (2 calls): ~$0.002
- **Total: ~$0.011**

---

## Section 3: Sound Library

### Ingestion Pipeline
```
Crawl MyInstants /vn/
→ Download MP3 + name + URL
→ LLM auto-tag (emotion, intensity, event_types, tags, description)
→ Text embedding → ChromaDB
→ Metadata → SQLite
```

### SQLite Schema
```sql
CREATE TABLE sounds (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  source_url    TEXT,
  file_path     TEXT NOT NULL,
  duration_ms   INTEGER,
  emotion       TEXT,       -- shock|sadness|hype|fail|awkward|dramatic|funny
  intensity     REAL,       -- 0.0 → 1.0
  timing_type   TEXT,       -- instant|buildup|reaction
  tags          TEXT,       -- JSON array
  event_types   TEXT,       -- JSON array
  description   TEXT,       -- for embedding
  use_count     INTEGER DEFAULT 0,
  accept_rate   REAL DEFAULT 0.0,
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### ChromaDB Collection
- **Document**: `"{description}. Tags: {tags}. Emotion: {emotion}. Events: {event_types}"`
- **Metadata**: `{emotion, intensity, timing_type, id}`
- **Embedding**: text-embedding-3-small (OpenRouter)

### Auto-Tag LLM Prompt
```
Bạn là chuyên gia về meme sound effects.
Sound name: "{name}", Duration: {duration_ms}ms
Trả về JSON: {emotion, intensity, timing_type, tags, event_types, description}
```

---

## Section 4: Highlight Detection

### Signal Ranking (effectiveness)
1. 🥇 Transcript keywords (shock words, profanity, reactions)
2. 🥇 Sudden audio spike (RMS delta)
3. 🥈 Silence → audio break (> 1000ms silence)
4. 🥈 Speech pause (> 1500ms)
5. 🥉 Scene change (frame diff)
6. 🥉 Facial expression (mediapipe)

### Scoring
- Each signal generates an `Event(timestamp_ms, score, type, emotion)`
- Events within 2000ms window are merged and scores summed (capped at 1.0)
- Filter: keep highlights with score > 0.5

### Highlight Object
```json
{
  "start_ms": 12400,
  "end_ms": 13100,
  "peak_ms": 12650,
  "score": 0.87,
  "event_type": "fail",
  "emotion": "shock",
  "intensity": 0.87,
  "signals": ["audio_spike", "speech_keyword"],
  "context_text": "wait what the— oh no"
}
```

### LLM Validation Pass
- Send all raw highlights + context to 1 LLM call
- LLM validates `keep: true/false` and enriches `event_type`

---

## Section 5: Sound Selection

### Hybrid Approach
1. **Stage 1 — Embedding Search**: ChromaDB query → top-5 candidates
2. **Stage 2 — LLM Re-rank**: choose best sound with comedic reasoning

### LLM Re-rank Prompt
```
HIGHLIGHT: {event_type}, {emotion}, intensity={intensity}
Context: "{context_text}"
CANDIDATES: [list of 5 sounds with descriptions]
Chọn sound phù hợp nhất. Ưu tiên comedic timing hơn semantic match.
Output: {"chosen_id": "...", "reason": "..."}
```

### Fallback
- No candidates → rule-based map `{emotion → default_sound}`
- 1 candidate → skip LLM, use directly

---

## Section 6: Timeline Placement

### Offset Rules by timing_type
| timing_type | Formula | Example |
|---|---|---|
| `instant` | `peak_ms - duration * 0.1` | Metal Pipe sync with fall |
| `reaction` | `end_ms + 200ms` | Bruh after awkward statement |
| `buildup` | `peak_ms - duration - 300ms` | Dramatic sting before reveal |

### Overlap Resolution
- Sort placements by `insert_ms`
- If next placement starts < 500ms after previous ends → keep higher confidence one

### Placement Object
```json
{
  "sound_file": "/sounds/metal_pipe.mp3",
  "insert_ms": 8440,
  "volume": 0.85,
  "fade_in_ms": 0,
  "fade_out_ms": 50
}
```

---

## Section 7: Evaluation Metrics

### Highlight Detection
- **Precision** > 70%: % detected highlights that are actually good
- **Recall** > 50%: % good moments caught
- **False Positive Rate** < 30%

### Sound Selection
- **Sound Relevance Score** > 3.5/5 (human eval)
- **Sound Replacement Rate** < 40%
- **Top-1 Accuracy** > 60%

### System
- **Processing Latency** < 3 min for 3-min video
- **User Acceptance Rate** > 50% (download without editing)
- **Cost per Video** < $0.05

### Feedback Loop
User actions (keep/replace/delete) per sound → stored in SQLite → used to improve thresholds and ranking in V2.

---

## Section 8: Future Versions

### Roadmap
| Component | MVP | V2 (1-3mo) | Production (3-6mo) |
|---|---|---|---|
| ASR | Whisper API | Whisper local | Streaming ASR |
| Highlight | Rule + LLM | Fine-tuned transformer | Dedicated model |
| Sound match | ChromaDB + LLM | ChromaDB + Learned Ranker | Custom embeddings |
| Infra | Single server | Docker + Redis | K8s + GPU fleet |

### Training Data Strategy
- **After MVP**: collect `{highlight_features → sound_accepted}` from user feedback
- **V2** (500+ examples): fine-tune highlight detector (DistilBERT)
- **Production** (10k+ examples): train sound ranker model, replace LLM re-rank

### When to Train Custom Models
- MVP: ❌ LLM is sufficient
- V2: ✅ fine-tune highlight detector
- Production: ✅ train ranker + detector, target latency < 30s/video

---

## Open Questions (Resolved)
- ✅ Video type: Short-form < 3 min
- ✅ Platform: Web app
- ✅ Models: OpenRouter
- ✅ Sound source: MyInstants /vn/
- ✅ Architecture: Approach B (Signal Pipeline + LLM Reasoning)
