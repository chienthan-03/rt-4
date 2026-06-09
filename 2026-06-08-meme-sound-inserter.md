# Meme Sound Auto-Inserter — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web app that automatically inserts meme sound effects into short-form videos at contextually appropriate moments.

**Architecture:** Signal Pipeline + LLM Reasoning hybrid. Video is decomposed into multiple parallel signals (transcript, audio peaks, facial expressions, scene changes), aggregated into scored highlights, matched to sounds via ChromaDB semantic search + Gemini Flash re-ranking, placed at precise timestamps, and rendered with ffmpeg.

**Tech Stack:** FastAPI, Celery, Redis, ffmpeg, moviepy, Whisper (OpenRouter), Gemini Flash (OpenRouter), librosa, mediapipe, ChromaDB, SQLite, Vanilla JS

**Spec:** `docs/specs/2026-06-08-meme-sound-inserter-design.md`

**Project Root:** `C:\Users\hampe\.gemini\antigravity\scratch\meme-sound-inserter\`

---

## File Structure

```
meme-sound-inserter/
├── tasks.py                      # Celery app + process_video task (root level, run from here)
├── backend/
│   ├── main.py                   # FastAPI app: /upload, /status, /download
│   ├── config.py                 # Settings from .env (OpenRouter key, paths)
│   ├── ingestion/
│   │   ├── __init__.py
│   │   └── extractor.py          # ffmpeg: extract WAV + frames from video
│   ├── signals/
│   │   ├── __init__.py
│   │   ├── transcript.py         # Whisper via OpenRouter → segments + timestamps
│   │   ├── audio_signals.py      # librosa: RMS peaks, silence detection
│   │   ├── visual_signals.py     # frame diff → scene changes
│   │   └── face_signals.py       # mediapipe: per-frame expression
│   ├── detection/
│   │   ├── __init__.py
│   │   ├── highlight_detector.py # Aggregate signals → scored Highlight objects
│   │   └── llm_validator.py      # Gemini Flash: validate + enrich highlights
│   ├── sound/
│   │   ├── __init__.py
│   │   ├── library.py            # SQLite + ChromaDB CRUD
│   │   ├── crawler.py            # MyInstants scraper
│   │   ├── tagger.py             # LLM auto-tag new sounds
│   │   └── selector.py           # Hybrid: ChromaDB search + LLM re-rank
│   ├── placement/
│   │   ├── __init__.py
│   │   └── placer.py             # Offset calc by timing_type + overlap resolution
│   ├── render/
│   │   ├── __init__.py
│   │   └── renderer.py           # ffmpeg: mix audio tracks + export MP4
│   └── db/
│       ├── __init__.py
│       ├── models.py             # SQLite init + queries
│       └── chroma.py             # ChromaDB client singleton
├── frontend/
│   ├── index.html                # Upload UI + status polling + download
│   ├── style.css
│   └── app.js
├── tests/
│   ├── conftest.py               # Shared fixtures
│   ├── test_extractor.py
│   ├── test_signals.py
│   ├── test_highlight_detector.py
│   ├── test_sound_selector.py
│   └── test_placer.py
├── scripts/
│   └── seed_sounds.py            # CLI: crawl + tag + store sounds
├── sounds/                       # Downloaded MP3s (gitignored)
├── uploads/                      # Uploaded videos (gitignored)
├── outputs/                      # Rendered videos (gitignored)
├── requirements.txt
├── .env.example
├── docker-compose.yml
└── README.md
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `backend/config.py`

- [ ] **Step 1: Create project directory**

```bash
mkdir C:\Users\hampe\.gemini\antigravity\scratch\meme-sound-inserter
cd C:\Users\hampe\.gemini\antigravity\scratch\meme-sound-inserter
mkdir backend\ingestion backend\signals backend\detection backend\sound backend\placement backend\render backend\db
mkdir frontend tests scripts sounds uploads outputs
```

- [ ] **Step 2: Create `requirements.txt`**

```
fastapi==0.110.0
uvicorn==0.29.0
celery==5.3.6
redis==5.0.3
python-multipart==0.0.9
moviepy==1.0.3
librosa==0.10.1
mediapipe==0.10.11
opencv-python==4.9.0.80
chromadb==0.4.24
openai==1.30.0        # openai client works with OpenRouter
requests==2.31.0
beautifulsoup4==4.12.3
pydantic-settings==2.2.1
python-dotenv==1.0.1
pytest==8.1.1
httpx==0.27.0         # for FastAPI test client
numpy==1.26.4
soundfile==0.12.1
```

- [ ] **Step 3: Create `.env.example`**

```env
OPENROUTER_API_KEY=your_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
WHISPER_MODEL=openai/whisper-large-v3
LLM_MODEL=google/gemini-2.0-flash
EMBED_MODEL=openai/text-embedding-3-small

REDIS_URL=redis://localhost:6379/0
DB_PATH=./backend/sounds.db
CHROMA_PATH=./backend/chroma_db
SOUNDS_DIR=./sounds
UPLOADS_DIR=./uploads
OUTPUTS_DIR=./outputs

MAX_VIDEO_SIZE_MB=500
MAX_VIDEO_DURATION_S=180
```

- [ ] **Step 4: Create `backend/config.py`**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    whisper_model: str = "openai/whisper-large-v3"
    llm_model: str = "google/gemini-2.0-flash"
    embed_model: str = "openai/text-embedding-3-small"
    redis_url: str = "redis://localhost:6379/0"
    db_path: str = "./backend/sounds.db"
    chroma_path: str = "./backend/chroma_db"
    sounds_dir: str = "./sounds"
    uploads_dir: str = "./uploads"
    outputs_dir: str = "./outputs"
    max_video_size_mb: int = 500
    max_video_duration_s: int = 180

    class Config:
        env_file = ".env"

settings = Settings()
```

- [ ] **Step 5: Create `docker-compose.yml`**

```yaml
version: "3.9"
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

- [ ] **Step 6: Initialize all `__init__.py` files**

```bash
# Create empty __init__.py in each backend subpackage
for dir in ingestion signals detection sound placement render db; do
  echo "" > backend/$dir/__init__.py
done
```

- [ ] **Step 7: Commit**

```bash
git init
echo "sounds/ uploads/ outputs/ .env *.db chroma_db/" > .gitignore
git add .
git commit -m "feat: project scaffolding"
```

---

## Task 2: Database Setup

**Files:**
- Create: `backend/db/models.py`
- Create: `backend/db/chroma.py`

- [ ] **Step 1: Write test for DB init**

```python
# tests/test_db.py
def test_sounds_table_created(tmp_path):
    from backend.db.models import init_db, get_sounds
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    sounds = get_sounds(db_path)
    assert sounds == []
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/test_db.py -v
```

- [ ] **Step 3: Create `backend/db/models.py`**

```python
import sqlite3
import json
from typing import Optional

def init_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sounds (
            id            TEXT PRIMARY KEY,
            name          TEXT NOT NULL,
            source_url    TEXT,
            file_path     TEXT NOT NULL,
            duration_ms   INTEGER,
            emotion       TEXT,
            intensity     REAL,
            timing_type   TEXT,
            tags          TEXT,
            event_types   TEXT,
            description   TEXT,
            use_count     INTEGER DEFAULT 0,
            accept_rate   REAL DEFAULT 0.0,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def insert_sound(db_path: str, sound: dict):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        INSERT OR REPLACE INTO sounds
        (id, name, source_url, file_path, duration_ms, emotion, intensity,
         timing_type, tags, event_types, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        sound["id"], sound["name"], sound.get("source_url"),
        sound["file_path"], sound.get("duration_ms"),
        sound.get("emotion"), sound.get("intensity"), sound.get("timing_type"),
        json.dumps(sound.get("tags", [])),
        json.dumps(sound.get("event_types", [])),
        sound.get("description")
    ))
    conn.commit()
    conn.close()

def get_sounds(db_path: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM sounds").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def update_sound_stats(db_path: str, sound_id: str, accepted: bool):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        UPDATE sounds SET
            use_count = use_count + 1,
            accept_rate = (accept_rate * use_count + ?) / (use_count + 1)
        WHERE id = ?
    """, (1.0 if accepted else 0.0, sound_id))
    conn.commit()
    conn.close()
```

- [ ] **Step 4: Create `backend/db/chroma.py`**

```python
import chromadb
from backend.config import settings

_client = None
_collection = None

def get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=settings.chroma_path)
        _collection = _client.get_or_create_collection(
            name="sounds",
            metadata={"hnsw:space": "cosine"}
        )
    return _collection

def add_sound_embedding(sound_id: str, document: str, metadata: dict):
    col = get_collection()
    col.add(ids=[sound_id], documents=[document], metadatas=[metadata])

def search_sounds(query: str, top_k: int = 5, where: dict = None) -> list[dict]:
    col = get_collection()
    kwargs = {"query_texts": [query], "n_results": top_k}
    if where:
        kwargs["where"] = where
    results = col.query(**kwargs)
    return [
        {"id": results["ids"][0][i], "distance": results["distances"][0][i],
         "metadata": results["metadatas"][0][i]}
        for i in range(len(results["ids"][0]))
    ]
```

- [ ] **Step 5: Run test — expect PASS**

```bash
pytest tests/test_db.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/db/ tests/test_db.py
git commit -m "feat: SQLite + ChromaDB setup"
```

---

## Task 3: Sound Crawler

**Files:**
- Create: `backend/sound/crawler.py`

- [ ] **Step 1: Write test**

```python
# tests/test_crawler.py
from unittest.mock import patch, MagicMock
from backend.sound.crawler import parse_sounds_from_html

SAMPLE_HTML = """
<div class="instant">
  <a class="instant-link" href="/instant/vine-boom/">Vine Boom</a>
  <button data-url="/media/sounds/vine-boom.mp3"></button>
</div>
"""

def test_parse_sounds_from_html():
    sounds = parse_sounds_from_html(SAMPLE_HTML, base_url="https://www.myinstants.com")
    assert len(sounds) == 1
    assert sounds[0]["name"] == "Vine Boom"
    assert "vine-boom.mp3" in sounds[0]["mp3_url"]
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/test_crawler.py -v
```

- [ ] **Step 3: Create `backend/sound/crawler.py`**

```python
import requests
from bs4 import BeautifulSoup
from pathlib import Path
import time

BASE_URL = "https://www.myinstants.com"
INDEX_URL = f"{BASE_URL}/en/index/vn/"

def parse_sounds_from_html(html: str, base_url: str = BASE_URL) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    sounds = []
    for instant in soup.select(".instant"):
        name_tag = instant.select_one(".instant-link")
        btn = instant.select_one("[data-url]")
        if not name_tag or not btn:
            continue
        name = name_tag.get_text(strip=True)
        mp3_url = btn.get("data-url", "")
        if mp3_url and not mp3_url.startswith("http"):
            mp3_url = base_url + mp3_url
        page_url = name_tag.get("href", "")
        if page_url and not page_url.startswith("http"):
            page_url = base_url + page_url
        sounds.append({"name": name, "mp3_url": mp3_url, "source_url": page_url})
    return sounds

def crawl_myinstants(max_pages: int = 10) -> list[dict]:
    all_sounds = []
    for page in range(1, max_pages + 1):
        url = f"{INDEX_URL}?page={page}"
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            sounds = parse_sounds_from_html(resp.text)
            if not sounds:
                break
            all_sounds.extend(sounds)
            time.sleep(1)  # polite crawling
        except Exception as e:
            print(f"Error on page {page}: {e}")
            break
    return all_sounds

def download_mp3(mp3_url: str, dest_dir: str, filename: str) -> str:
    Path(dest_dir).mkdir(parents=True, exist_ok=True)
    dest = str(Path(dest_dir) / filename)
    resp = requests.get(mp3_url, timeout=15)
    resp.raise_for_status()
    with open(dest, "wb") as f:
        f.write(resp.content)
    return dest
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/test_crawler.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/sound/crawler.py tests/test_crawler.py
git commit -m "feat: MyInstants crawler"
```

---

## Task 4: Sound Tagger (LLM Auto-Tag)

**Files:**
- Create: `backend/sound/tagger.py`

- [ ] **Step 1: Write test**

```python
# tests/test_tagger.py
from unittest.mock import patch

def test_build_tag_prompt():
    from backend.sound.tagger import build_tag_prompt
    prompt = build_tag_prompt("Vine Boom", 450)
    assert "Vine Boom" in prompt
    assert "450" in prompt
    assert "emotion" in prompt

def test_parse_tag_response():
    from backend.sound.tagger import parse_tag_response
    raw = '{"emotion": "shock", "intensity": 0.9, "timing_type": "instant", "tags": ["impact"], "event_types": ["fall"], "description": "short boom"}'
    result = parse_tag_response(raw)
    assert result["emotion"] == "shock"
    assert result["intensity"] == 0.9
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/test_tagger.py -v
```

- [ ] **Step 3: Create `backend/sound/tagger.py`**

```python
import json
from openai import OpenAI
from backend.config import settings

client = OpenAI(
    api_key=settings.openrouter_api_key,
    base_url=settings.openrouter_base_url
)

def build_tag_prompt(name: str, duration_ms: int) -> str:
    return f"""Bạn là chuyên gia về meme sound effects. 

Sound name: "{name}"
Duration: {duration_ms}ms

Phân tích và trả về JSON với các trường sau:
{{
  "emotion": "shock|sadness|hype|fail|awkward|dramatic|funny|cringe|win",
  "intensity": 0.0-1.0,
  "timing_type": "instant|buildup|reaction",
  "tags": ["tag1", "tag2"],
  "event_types": ["event1", "event2"],
  "description": "mô tả ngắn để embedding search"
}}

Chỉ trả về JSON, không giải thích."""

def parse_tag_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

def tag_sound(name: str, duration_ms: int) -> dict:
    prompt = build_tag_prompt(name, duration_ms)
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    raw = response.choices[0].message.content
    return parse_tag_response(raw)
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/test_tagger.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/sound/tagger.py tests/test_tagger.py
git commit -m "feat: LLM sound auto-tagger"
```

---

## Task 5: Sound Library + Seed Script

**Files:**
- Create: `backend/sound/library.py`
- Test: `tests/test_library.py`
- Create: `scripts/seed_sounds.py`

- [ ] **Step 1: Write tests for library helpers**

```python
# tests/test_library.py
def test_build_chroma_document_contains_all_fields():
    from backend.sound.library import build_chroma_document
    sound = {
        "description": "Short boom",
        "tags": ["impact", "meme"],
        "emotion": "shock",
        "event_types": ["fall", "fail"]
    }
    doc = build_chroma_document(sound)
    assert "Short boom" in doc
    assert "impact" in doc
    assert "shock" in doc
    assert "fall" in doc

def test_build_chroma_document_handles_missing_fields():
    from backend.sound.library import build_chroma_document
    doc = build_chroma_document({})  # no fields — must not raise
    assert isinstance(doc, str)
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/test_library.py -v
```

- [ ] **Step 3: Create `backend/sound/library.py`**

```python
import uuid
import librosa
from pathlib import Path
from backend.db.models import init_db, insert_sound, get_sounds
from backend.db.chroma import add_sound_embedding
from backend.config import settings

def get_audio_duration_ms(file_path: str) -> int:
    y, sr = librosa.load(file_path, sr=None, mono=True)
    return int(len(y) / sr * 1000)

def build_chroma_document(sound: dict) -> str:
    tags = ", ".join(sound.get("tags", []))
    events = ", ".join(sound.get("event_types", []))
    return (
        f"{sound.get('description', '')}. "
        f"Tags: {tags}. Emotion: {sound.get('emotion')}. "
        f"Events: {events}."
    )

def add_sound_to_library(name: str, file_path: str, source_url: str, tag_data: dict):
    init_db(settings.db_path)
    sound_id = str(uuid.uuid4())
    duration_ms = get_audio_duration_ms(file_path)
    sound = {
        "id": sound_id,
        "name": name,
        "source_url": source_url,
        "file_path": file_path,
        "duration_ms": duration_ms,
        **tag_data
    }
    insert_sound(settings.db_path, sound)
    doc = build_chroma_document(sound)
    add_sound_embedding(sound_id, doc, {
        "emotion": tag_data.get("emotion", ""),
        "intensity": float(tag_data.get("intensity", 0.5)),
        "timing_type": tag_data.get("timing_type", "instant"),
        "name": name,
        "file_path": file_path,
        "duration_ms": duration_ms
    })
    return sound_id
```

- [ ] **Step 2: Create `scripts/seed_sounds.py`**

```python
"""
Usage: python scripts/seed_sounds.py --pages 5
Crawls MyInstants, downloads sounds, tags them, stores in DB.
"""
import argparse
import sys
sys.path.insert(0, ".")

from backend.sound.crawler import crawl_myinstants, download_mp3
from backend.sound.tagger import tag_sound
from backend.sound.library import add_sound_to_library
from backend.config import settings
from pathlib import Path
import time

def main(max_pages: int):
    print(f"Crawling MyInstants (max {max_pages} pages)...")
    sounds = crawl_myinstants(max_pages=max_pages)
    print(f"Found {len(sounds)} sounds")

    for i, s in enumerate(sounds):
        try:
            filename = Path(s["mp3_url"]).name
            file_path = download_mp3(s["mp3_url"], settings.sounds_dir, filename)
            from backend.sound.library import get_audio_duration_ms
            real_duration_ms = get_audio_duration_ms(file_path)  # use real duration
            tags = tag_sound(s["name"], duration_ms=real_duration_ms)
            sound_id = add_sound_to_library(s["name"], file_path, s["source_url"], tags)
            print(f"[{i+1}/{len(sounds)}] Added: {s['name']} ({sound_id[:8]}...)")
            time.sleep(0.5)
        except Exception as e:
            print(f"[{i+1}/{len(sounds)}] SKIP {s['name']}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=5)
    args = parser.parse_args()
    main(args.pages)
```

- [ ] **Step 3: Commit**

```bash
git add backend/sound/library.py scripts/seed_sounds.py
git commit -m "feat: sound library + seed script"
```

---

## Task 6: Video Ingestion (Extract Audio + Frames)

**Files:**
- Create: `backend/ingestion/extractor.py`

- [ ] **Step 1: Write test**

```python
# tests/test_extractor.py
import pytest
from pathlib import Path

def test_extract_audio_creates_wav(tmp_path, sample_video_path):
    from backend.ingestion.extractor import extract_audio
    wav_path = extract_audio(sample_video_path, str(tmp_path))
    assert Path(wav_path).exists()
    assert wav_path.endswith(".wav")

def test_extract_frames_returns_list(tmp_path, sample_video_path):
    from backend.ingestion.extractor import extract_frames
    frames = extract_frames(sample_video_path, str(tmp_path), fps=1)
    assert len(frames) > 0
    assert all(Path(f).exists() for f in frames)
```

> **Note:** `sample_video_path` fixture in `conftest.py` should point to a small test video (create a 3-second synthetic video with moviepy in the fixture).

- [ ] **Step 2: Create `tests/conftest.py`**

```python
import pytest
import numpy as np
from moviepy.editor import ColorClip, AudioClip, CompositeAudioClip

@pytest.fixture(scope="session")
def sample_video_path(tmp_path_factory):
    """3-second test video with a sine wave audio track."""
    tmp = tmp_path_factory.mktemp("video")
    path = str(tmp / "test.mp4")
    # Create video with visible color
    video = ColorClip(size=(640, 480), color=(0, 100, 200), duration=3)
    # Create sine wave audio (440Hz) so WAV extraction produces non-empty audio
    def make_sine(t):
        return [np.sin(2 * np.pi * 440 * t), np.sin(2 * np.pi * 440 * t)]
    audio = AudioClip(make_sine, duration=3, fps=44100)
    video = video.set_audio(audio)
    video.write_videofile(path, fps=24, logger=None, codec="libx264", audio_codec="aac")
    return path
```

- [ ] **Step 3: Create `backend/ingestion/extractor.py`**

```python
import subprocess
from pathlib import Path

def extract_audio(video_path: str, output_dir: str) -> str:
    """Extract mono 16kHz WAV from video."""
    out = str(Path(output_dir) / (Path(video_path).stem + ".wav"))
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path,
        "-ar", "16000", "-ac", "1", "-vn", out
    ], check=True, capture_output=True)
    return out

def extract_frames(video_path: str, output_dir: str, fps: float = 1.0) -> list[str]:
    """Extract frames at given fps. Returns list of jpg paths."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    pattern = str(Path(output_dir) / "frame_%04d.jpg")
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"fps={fps}", pattern
    ], check=True, capture_output=True)
    return sorted(str(p) for p in Path(output_dir).glob("frame_*.jpg"))

def get_video_duration_s(video_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    result = subprocess.run([
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", video_path
    ], capture_output=True, text=True, check=True)
    import json
    data = json.loads(result.stdout)
    for s in data["streams"]:
        if s.get("codec_type") == "video":
            return float(s["duration"])
    return 0.0
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_extractor.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/ingestion/ tests/test_extractor.py tests/conftest.py
git commit -m "feat: video ingestion (audio + frame extraction)"
```

---

## Task 7: Signal Extraction — Transcript

**Files:**
- Create: `backend/signals/transcript.py`

- [ ] **Step 1: Write test**

```python
# tests/test_signals.py
from unittest.mock import patch, MagicMock

def test_parse_whisper_response():
    from backend.signals.transcript import parse_whisper_segments
    mock_response = {
        "segments": [
            {"start": 0.0, "end": 1.5, "text": "oh no"},
            {"start": 2.0, "end": 3.0, "text": "what happened"}
        ]
    }
    segments = parse_whisper_segments(mock_response)
    assert len(segments) == 2
    assert segments[0]["text"] == "oh no"
    assert segments[0]["start_ms"] == 0

def test_keyword_score():
    from backend.signals.transcript import keyword_score
    assert keyword_score("oh no oh no") > 0.5
    assert keyword_score("the weather is nice") == 0.0
```

- [ ] **Step 2: Create `backend/signals/transcript.py`**

```python
from openai import OpenAI
from backend.config import settings

client = OpenAI(
    api_key=settings.openrouter_api_key,
    base_url=settings.openrouter_base_url
)

SHOCK_KEYWORDS = [
    "oh no", "bruh", "wait what", "what the", "no way", "oh my god", "omg",
    "wtf", "noooo", "yikes", "oof", "ouch", "bro", "dude", "seriously",
    "không thể tin", "trời ơi", "ôi trời", "thôi rồi", "chết rồi"
]

def transcribe(audio_path: str) -> dict:
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            model=settings.whisper_model,
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["segment"]
        )
    return response.model_dump()

def parse_whisper_segments(response: dict) -> list[dict]:
    return [
        {
            "start_ms": int(s["start"] * 1000),
            "end_ms": int(s["end"] * 1000),
            "text": s["text"].strip()
        }
        for s in response.get("segments", [])
    ]

def keyword_score(text: str) -> float:
    text_lower = text.lower()
    score = 0.0
    for kw in SHOCK_KEYWORDS:
        if kw in text_lower:
            score += 0.3
    return min(score, 1.0)

def extract_transcript_events(segments: list[dict]) -> list[dict]:
    events = []
    for seg in segments:
        score = keyword_score(seg["text"])
        if score > 0:
            events.append({
                "timestamp_ms": seg["start_ms"],
                "end_ms": seg["end_ms"],
                "score": score,
                "type": "speech_keyword",
                "context_text": seg["text"]
            })
    return events
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_signals.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/signals/transcript.py tests/test_signals.py
git commit -m "feat: transcript signal extraction"
```

---

## Task 8: Signal Extraction — Audio + Visual + Face

**Files:**
- Create: `backend/signals/audio_signals.py`
- Create: `backend/signals/visual_signals.py`
- Create: `backend/signals/face_signals.py`
- Test: `tests/test_audio_signals.py`

- [ ] **Step 1: Write tests for audio signal extractor**

```python
# tests/test_audio_signals.py
import numpy as np
import soundfile as sf
from pathlib import Path

def test_extract_audio_events_returns_list(tmp_path):
    """Silent WAV should return empty list (no spikes)."""
    from backend.signals.audio_signals import extract_audio_events
    wav_path = str(tmp_path / "silent.wav")
    silent = np.zeros(16000 * 3, dtype=np.float32)  # 3s silence
    sf.write(wav_path, silent, 16000)
    events = extract_audio_events(wav_path)
    assert isinstance(events, list)
    # All events must have required keys
    for e in events:
        assert "timestamp_ms" in e
        assert "score" in e
        assert "type" in e

def test_extract_audio_events_detects_spike(tmp_path):
    """A sudden loud segment after silence should produce an audio_spike event."""
    from backend.signals.audio_signals import extract_audio_events
    wav_path = str(tmp_path / "spike.wav")
    sr = 16000
    silence = np.zeros(sr, dtype=np.float32)           # 1s silence
    spike = np.sin(2 * np.pi * 440 * np.linspace(0, 0.5, sr // 2)).astype(np.float32)  # 0.5s tone
    audio = np.concatenate([silence, spike])
    sf.write(wav_path, audio, sr)
    events = extract_audio_events(wav_path)
    spike_events = [e for e in events if e["type"] == "audio_spike"]
    assert len(spike_events) > 0
```

> **Note:** Add `soundfile==0.12.1` to `requirements.txt` — needed for test WAV writing. librosa uses it internally too.

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/test_audio_signals.py -v
```

- [ ] **Step 3: Create `backend/signals/audio_signals.py`**

```python
import librosa
import numpy as np

def extract_audio_events(wav_path: str) -> list[dict]:
    y, sr = librosa.load(wav_path, sr=16000, mono=True)
    events = []

    # RMS energy per frame
    hop_length = 512
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    times_ms = (librosa.frames_to_time(
        np.arange(len(rms)), sr=sr, hop_length=hop_length
    ) * 1000).astype(int)

    # Detect spikes: where RMS jumps by > 2 std
    mean_rms = np.mean(rms)
    std_rms = np.std(rms)
    threshold = mean_rms + 2 * std_rms

    for i in range(1, len(rms)):
        if rms[i] > threshold and rms[i] > rms[i-1] * 1.5:
            score = min((rms[i] - threshold) / (std_rms + 1e-6) * 0.3, 1.0)
            events.append({
                "timestamp_ms": int(times_ms[i]),
                "score": float(score),
                "type": "audio_spike",
                "context_text": ""
            })

    # Detect silence breaks (> 1000ms silence → sound)
    intervals = librosa.effects.split(y, top_db=30)
    for start, end in intervals:
        start_ms = int(start / sr * 1000)
        # silence before this interval
        if start_ms > 1000:
            events.append({
                "timestamp_ms": start_ms,
                "score": 0.5,
                "type": "silence_break",
                "context_text": ""
            })

    return events
```

- [ ] **Step 2: Create `backend/signals/visual_signals.py`**

```python
import cv2
import numpy as np
from pathlib import Path

def extract_scene_change_events(frames_dir: str, threshold: float = 30.0) -> list[dict]:
    frame_paths = sorted(Path(frames_dir).glob("frame_*.jpg"))
    events = []
    prev_gray = None

    for i, fp in enumerate(frame_paths):
        frame = cv2.imread(str(fp), cv2.IMREAD_GRAYSCALE)
        if frame is None:
            continue
        if prev_gray is not None:
            diff = np.mean(np.abs(frame.astype(float) - prev_gray.astype(float)))
            if diff > threshold:
                # frame index → approximate ms (assuming 1fps extraction)
                events.append({
                    "timestamp_ms": i * 1000,
                    "score": min(diff / 100.0, 0.6),
                    "type": "scene_change",
                    "context_text": ""
                })
        prev_gray = frame

    return events
```

- [ ] **Step 3: Create `backend/signals/face_signals.py`**

```python
import cv2
import mediapipe as mp
from pathlib import Path

mp_face = mp.solutions.face_detection

def extract_face_events(frames_dir: str) -> list[dict]:
    frame_paths = sorted(Path(frames_dir).glob("frame_*.jpg"))
    events = []

    with mp_face.FaceDetection(min_detection_confidence=0.5) as detector:
        for i, fp in enumerate(frame_paths):
            frame = cv2.imread(str(fp))
            if frame is None:
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = detector.process(rgb)
            if results.detections:
                # Face detected — low baseline score, enriched by other signals
                events.append({
                    "timestamp_ms": i * 1000,
                    "score": 0.2,
                    "type": "face_detected",
                    "context_text": ""
                })

    return events
```

- [ ] **Step 4: Commit**

```bash
git add backend/signals/
git commit -m "feat: audio, visual, face signal extractors"
```

---

## Task 9: Highlight Detector

**Files:**
- Create: `backend/detection/highlight_detector.py`

- [ ] **Step 1: Write test**

```python
# tests/test_highlight_detector.py
from backend.detection.highlight_detector import merge_events, score_to_highlight

def test_merge_nearby_events():
    events = [
        {"timestamp_ms": 1000, "score": 0.6, "type": "audio_spike", "context_text": ""},
        {"timestamp_ms": 1500, "score": 0.7, "type": "speech_keyword", "context_text": "oh no"},
    ]
    merged = merge_events(events, window_ms=2000)
    assert len(merged) == 1
    assert merged[0]["score"] > 0.6

def test_far_events_not_merged():
    events = [
        {"timestamp_ms": 1000, "score": 0.6, "type": "audio_spike", "context_text": ""},
        {"timestamp_ms": 5000, "score": 0.7, "type": "speech_keyword", "context_text": "bruh"},
    ]
    merged = merge_events(events, window_ms=2000)
    assert len(merged) == 2
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/test_highlight_detector.py -v
```

- [ ] **Step 3: Create `backend/detection/highlight_detector.py`**

```python
from dataclasses import dataclass, field

EMOTION_MAP = {
    "speech_keyword": "shock",
    "audio_spike": "shock",
    "silence_break": "dramatic",
    "scene_change": "neutral",
    "face_detected": "neutral"
}

@dataclass
class Highlight:
    start_ms: int
    end_ms: int
    peak_ms: int
    score: float
    event_type: str = "unknown"
    emotion: str = "shock"
    intensity: float = 0.5
    signals: list = field(default_factory=list)
    context_text: str = ""

def merge_events(events: list[dict], window_ms: int = 2000) -> list[dict]:
    if not events:
        return []
    events = sorted(events, key=lambda e: e["timestamp_ms"])
    groups = [[events[0]]]

    for ev in events[1:]:
        if ev["timestamp_ms"] - groups[-1][-1]["timestamp_ms"] <= window_ms:
            groups[-1].append(ev)
        else:
            groups.append([ev])

    merged = []
    for group in groups:
        score = min(sum(e["score"] for e in group), 1.0)
        peak = max(group, key=lambda e: e["score"])
        context = " ".join(e["context_text"] for e in group if e["context_text"]).strip()
        merged.append({
            "timestamp_ms": group[0]["timestamp_ms"],
            "end_ms": group[-1]["timestamp_ms"] + 500,
            "peak_ms": peak["timestamp_ms"],
            "score": score,
            "signals": [e["type"] for e in group],
            "context_text": context
        })
    return merged

def score_to_highlight(merged_event: dict) -> Highlight:
    return Highlight(
        start_ms=merged_event["timestamp_ms"],
        end_ms=merged_event["end_ms"],
        peak_ms=merged_event["peak_ms"],
        score=merged_event["score"],
        intensity=merged_event["score"],
        signals=merged_event["signals"],
        context_text=merged_event["context_text"]
    )

def detect_highlights(all_events: list[dict], threshold: float = 0.5) -> list[Highlight]:
    merged = merge_events(all_events, window_ms=2000)
    return [
        score_to_highlight(e) for e in merged
        if e["score"] >= threshold
    ]
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/test_highlight_detector.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/detection/highlight_detector.py tests/test_highlight_detector.py
git commit -m "feat: highlight detector (event aggregation + scoring)"
```

---

## Task 10: LLM Validator

**Files:**
- Create: `backend/detection/llm_validator.py`
- Test: `tests/test_llm_validator.py`

- [ ] **Step 1: Write tests for JSON parsing logic**

```python
# tests/test_llm_validator.py
def test_strip_plain_json():
    """Plain JSON response (no fences) should parse correctly."""
    from backend.detection.llm_validator import _parse_decisions
    raw = '[{"index": 0, "keep": true, "event_type": "fail", "emotion": "shock"}]'
    decisions = _parse_decisions(raw)
    assert decisions[0]["keep"] is True
    assert decisions[0]["event_type"] == "fail"

def test_strip_json_fence():
    """```json fence should be stripped before parsing."""
    from backend.detection.llm_validator import _parse_decisions
    raw = '```json\n[{"index": 0, "keep": false, "event_type": "generic", "emotion": "neutral"}]\n```'
    decisions = _parse_decisions(raw)
    assert decisions[0]["keep"] is False

def test_strip_plain_fence():
    """Plain ``` fence (no 'json' label) should also be stripped."""
    from backend.detection.llm_validator import _parse_decisions
    raw = '```\n[{"index": 0, "keep": true, "event_type": "shock", "emotion": "shock"}]\n```'
    decisions = _parse_decisions(raw)
    assert len(decisions) == 1
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/test_llm_validator.py -v
```

- [ ] **Step 3: Create `backend/detection/llm_validator.py`**

```python
import json
from openai import OpenAI
from backend.config import settings
from backend.detection.highlight_detector import Highlight

client = OpenAI(
    api_key=settings.openrouter_api_key,
    base_url=settings.openrouter_base_url
)

def _parse_decisions(raw: str) -> list[dict]:
    """Parse LLM JSON response, stripping markdown fences if present."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

def validate_highlights(highlights: list[Highlight]) -> list[Highlight]:
    if not highlights:
        return []

    items = [
        {
            "index": i,
            "peak_ms": h.peak_ms,
            "score": h.score,
            "signals": h.signals,
            "context": h.context_text
        }
        for i, h in enumerate(highlights)
    ]

    prompt = f"""Bạn đang review các khoảnh khắc được phát hiện trong video để chèn meme sound.

Danh sách highlights:
{json.dumps(items, ensure_ascii=False, indent=2)}

Với mỗi highlight, quyết định:
- keep: true/false (có xứng đáng chèn sound không)
- event_type: fall|fail|shock|win|awkward|cringe|emotional|funny|plot_twist|generic
- emotion: shock|sadness|hype|fail|awkward|dramatic|funny

Trả về JSON array: [{{"index": 0, "keep": true, "event_type": "...", "emotion": "..."}}]
Chỉ trả về JSON array."""

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    raw = response.choices[0].message.content.strip()
    decisions = _parse_decisions(raw)
    result = []
    for d in decisions:
        if d.get("keep"):
            h = highlights[d["index"]]
            h.event_type = d.get("event_type", h.event_type)
            h.emotion = d.get("emotion", h.emotion)
            result.append(h)
    return result
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/test_llm_validator.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/detection/llm_validator.py tests/test_llm_validator.py
git commit -m "feat: LLM highlight validator + enricher"
```

---

## Task 11: Sound Selector (Hybrid)

**Files:**
- Create: `backend/sound/selector.py`

- [ ] **Step 1: Write test**

```python
# tests/test_sound_selector.py
from unittest.mock import patch, MagicMock
from backend.sound.selector import build_search_query, apply_fallback_rule

def test_build_search_query():
    from backend.detection.highlight_detector import Highlight
    h = Highlight(0, 1000, 500, 0.8, "fail", "shock", 0.8, ["audio_spike"], "oh no")
    q = build_search_query(h)
    assert "fail" in q
    assert "shock" in q

def test_fallback_rule_returns_something():
    result = apply_fallback_rule("shock")
    assert result is not None
```

- [ ] **Step 2: Create `backend/sound/selector.py`**

```python
import json
from openai import OpenAI
from backend.config import settings
from backend.db.chroma import search_sounds
from backend.detection.highlight_detector import Highlight

client = OpenAI(
    api_key=settings.openrouter_api_key,
    base_url=settings.openrouter_base_url
)

FALLBACK_RULES = {
    "shock": "vine_boom",
    "fail": "metal_pipe",
    "sadness": "sad_violin",
    "hype": "crowd_cheer",
    "awkward": "bruh",
    "dramatic": "sad_violin",
}

def build_search_query(highlight: Highlight) -> str:
    return f"{highlight.event_type} {highlight.emotion} intensity={highlight.intensity:.1f}"

def apply_fallback_rule(emotion: str) -> dict | None:
    sound_name = FALLBACK_RULES.get(emotion)
    if not sound_name:
        return None
    return {"name": sound_name, "fallback": True}

def llm_rerank(highlight: Highlight, candidates: list[dict]) -> dict:
    items = [
        f"{i+1}. ID={c['id']} Name={c['metadata'].get('name')} "
        f"({c['metadata'].get('emotion')}, intensity={c['metadata'].get('intensity'):.1f}, "
        f"type={c['metadata'].get('timing_type')})"
        for i, c in enumerate(candidates)
    ]
    prompt = f"""Chọn meme sound phù hợp nhất cho moment này:

HIGHLIGHT:
- Event: {highlight.event_type}
- Emotion: {highlight.emotion}
- Intensity: {highlight.intensity:.1f}/1.0
- Context: "{highlight.context_text}"

CANDIDATES:
{chr(10).join(items)}

Ưu tiên comedic timing và cultural fit với meme context.
Output JSON: {{"chosen_id": "...", "reason": "..."}}"""

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

def select_sound(highlight: Highlight) -> dict | None:
    query = build_search_query(highlight)
    candidates = search_sounds(query, top_k=5)

    if not candidates:
        return apply_fallback_rule(highlight.emotion)

    if len(candidates) == 1:
        c = candidates[0]
        return {"chosen_id": c["id"], "metadata": c["metadata"]}

    result = llm_rerank(highlight, candidates)
    chosen_id = result["chosen_id"]
    meta = next((c["metadata"] for c in candidates if c["id"] == chosen_id), None)
    return {"chosen_id": chosen_id, "metadata": meta, "reason": result.get("reason")}
```

- [ ] **Step 3: Run test**

```bash
pytest tests/test_sound_selector.py -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/sound/selector.py tests/test_sound_selector.py
git commit -m "feat: hybrid sound selector (ChromaDB + LLM re-rank)"
```

---

## Task 12: Timeline Placer

**Files:**
- Create: `backend/placement/placer.py`

- [ ] **Step 1: Write test**

```python
# tests/test_placer.py
from backend.placement.placer import calculate_insert_ms, resolve_overlaps

def test_instant_timing():
    insert_ms = calculate_insert_ms(peak_ms=8500, sound_duration_ms=600, timing_type="instant")
    assert insert_ms == 8500 - int(600 * 0.1)

def test_reaction_timing():
    insert_ms = calculate_insert_ms(peak_ms=8500, sound_duration_ms=800, timing_type="reaction", end_ms=9000)
    assert insert_ms == 9000 + 200

def test_resolve_overlaps_keeps_higher_confidence():
    placements = [
        {"insert_ms": 1000, "end_ms": 1600, "confidence": 0.7, "sound_file": "a.mp3"},
        {"insert_ms": 1400, "end_ms": 2200, "confidence": 0.9, "sound_file": "b.mp3"},
    ]
    resolved = resolve_overlaps(placements)
    assert len(resolved) == 1
    assert resolved[0]["sound_file"] == "b.mp3"
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/test_placer.py -v
```

- [ ] **Step 3: Create `backend/placement/placer.py`**

```python
from backend.detection.highlight_detector import Highlight

def calculate_insert_ms(
    peak_ms: int,
    sound_duration_ms: int,
    timing_type: str,
    end_ms: int = None
) -> int:
    if timing_type == "instant":
        return peak_ms - int(sound_duration_ms * 0.1)
    elif timing_type == "reaction":
        base = end_ms if end_ms else peak_ms
        return base + 200
    elif timing_type == "buildup":
        return peak_ms - sound_duration_ms - 300
    return peak_ms

def resolve_overlaps(placements: list[dict], min_gap_ms: int = 500) -> list[dict]:
    placements = sorted(placements, key=lambda p: p["insert_ms"])
    result = []
    for p in placements:
        if not result:
            result.append(p)
            continue
        prev = result[-1]
        if p["insert_ms"] < prev["end_ms"] + min_gap_ms:
            if p.get("confidence", 0) > prev.get("confidence", 0):
                result[-1] = p
        else:
            result.append(p)
    return result

def create_placements(
    highlights: list[Highlight],
    sound_selections: list[dict]
) -> list[dict]:
    placements = []
    for h, sel in zip(highlights, sound_selections):
        if not sel:
            continue
        meta = sel.get("metadata", {})
        duration_ms = meta.get("duration_ms", 1000)
        timing_type = meta.get("timing_type", "instant")
        file_path = meta.get("file_path", "")

        insert_ms = calculate_insert_ms(h.peak_ms, duration_ms, timing_type, h.end_ms)
        insert_ms = max(0, insert_ms)

        placements.append({
            "sound_file": file_path,
            "insert_ms": insert_ms,
            "end_ms": insert_ms + duration_ms,
            "volume": 0.85,
            "fade_in_ms": 0,
            "fade_out_ms": 50,
            "confidence": h.score
        })

    return resolve_overlaps(placements)
```

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/test_placer.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/placement/placer.py tests/test_placer.py
git commit -m "feat: timeline placer with offset rules + overlap resolution"
```

---

## Task 13: ffmpeg Renderer

**Files:**
- Create: `backend/render/renderer.py`
- Test: `tests/test_renderer.py`

- [ ] **Step 1: Write test for `build_ffmpeg_filter` (pure Python, no subprocess)**

```python
# tests/test_renderer.py
def test_build_ffmpeg_filter_single_placement():
    from backend.render.renderer import build_ffmpeg_filter
    placements = [{
        "sound_file": "/sounds/vine_boom.mp3",
        "insert_ms": 3000,
        "volume": 0.85,
        "fade_out_ms": 50
    }]
    filter_str, inputs = build_ffmpeg_filter(placements, original_duration_s=10.0)
    assert "-i" in inputs
    assert "/sounds/vine_boom.mp3" in inputs
    assert "adelay=3000" in filter_str
    assert "amix" in filter_str
    assert "[aout]" in filter_str

def test_build_ffmpeg_filter_multiple_placements():
    from backend.render.renderer import build_ffmpeg_filter
    placements = [
        {"sound_file": "/a.mp3", "insert_ms": 1000, "volume": 0.8, "fade_out_ms": 0},
        {"sound_file": "/b.mp3", "insert_ms": 5000, "volume": 0.9, "fade_out_ms": 100},
    ]
    filter_str, inputs = build_ffmpeg_filter(placements, original_duration_s=15.0)
    assert inputs.count("-i") == 2
    assert "sfx0" in filter_str
    assert "sfx1" in filter_str
    assert f"inputs=3" in filter_str  # [0:a] + sfx0 + sfx1

def test_build_ffmpeg_filter_empty_placements():
    from backend.render.renderer import build_ffmpeg_filter
    filter_str, inputs = build_ffmpeg_filter([], original_duration_s=10.0)
    assert inputs == []
    assert "amix=inputs=1" in filter_str  # just [0:a]
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/test_renderer.py -v
```

- [ ] **Step 3: Create `backend/render/renderer.py`**

```python
import subprocess
import tempfile
import os
from pathlib import Path

def build_ffmpeg_filter(placements: list[dict], original_duration_s: float) -> tuple[str, list[str]]:
    """Build ffmpeg filter_complex string for mixing sound effects."""
    inputs = []
    filter_parts = []
    amix_inputs = ["[0:a]"]

    for i, p in enumerate(placements):
        idx = i + 1
        offset_s = p["insert_ms"] / 1000.0
        volume = p["volume"]
        fade_out_s = p["fade_out_ms"] / 1000.0
        inputs.extend(["-i", p["sound_file"]])

        filter_parts.append(
            f"[{idx}:a]volume={volume},adelay={p['insert_ms']}|{p['insert_ms']},"
            f"apad=whole_dur={original_duration_s}[sfx{i}]"
        )
        amix_inputs.append(f"[sfx{i}]")

    mix = "".join(f"{p};" for p in filter_parts)
    mix += f"{''.join(amix_inputs)}amix=inputs={len(amix_inputs)}:duration=first:normalize=0[aout]"
    return mix, inputs

def render_video(
    input_video: str,
    placements: list[dict],
    output_path: str
) -> str:
    if not placements:
        # No sounds — just copy
        subprocess.run(["ffmpeg", "-y", "-i", input_video, "-c", "copy", output_path],
                       check=True, capture_output=True)
        return output_path

    # Get video duration
    result = subprocess.run([
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", input_video
    ], capture_output=True, text=True, check=True)
    duration_s = float(result.stdout.strip())

    filter_complex, sound_inputs = build_ffmpeg_filter(placements, duration_s)

    cmd = [
        "ffmpeg", "-y",
        "-i", input_video,
        *sound_inputs,
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path
```

- [ ] **Step 2: Commit**

```bash
git add backend/render/renderer.py
git commit -m "feat: ffmpeg audio mixer + renderer"
```

---

## Task 14: Celery Pipeline Orchestration

**Files:**
- Create: `tasks.py` (root level, Celery app)

- [ ] **Step 1: Create `tasks.py`**

```python
from celery import Celery
from backend.config import settings
import os, uuid, shutil
from pathlib import Path

app = Celery("meme_inserter", broker=settings.redis_url, backend=settings.redis_url)

@app.task(bind=True)
def process_video(self, video_path: str, job_id: str):
    work_dir = f"{settings.uploads_dir}/{job_id}"
    Path(work_dir).mkdir(parents=True, exist_ok=True)

    try:
        self.update_state(state="PROGRESS", meta={"step": "extracting"})
        from backend.ingestion.extractor import extract_audio, extract_frames, get_video_duration_s
        wav_path = extract_audio(video_path, work_dir)
        frames_dir = f"{work_dir}/frames"
        frames = extract_frames(video_path, frames_dir, fps=1)

        self.update_state(state="PROGRESS", meta={"step": "transcribing"})
        from backend.signals.transcript import transcribe, parse_whisper_segments, extract_transcript_events
        raw_transcript = transcribe(wav_path)
        segments = parse_whisper_segments(raw_transcript)
        transcript_events = extract_transcript_events(segments)

        self.update_state(state="PROGRESS", meta={"step": "analyzing_signals"})
        from backend.signals.audio_signals import extract_audio_events
        from backend.signals.visual_signals import extract_scene_change_events
        from backend.signals.face_signals import extract_face_events
        audio_events = extract_audio_events(wav_path)
        visual_events = extract_scene_change_events(frames_dir)
        face_events = extract_face_events(frames_dir)

        all_events = transcript_events + audio_events + visual_events + face_events

        self.update_state(state="PROGRESS", meta={"step": "detecting_highlights"})
        from backend.detection.highlight_detector import detect_highlights
        from backend.detection.llm_validator import validate_highlights
        raw_highlights = detect_highlights(all_events)
        highlights = validate_highlights(raw_highlights)

        self.update_state(state="PROGRESS", meta={"step": "selecting_sounds"})
        from backend.sound.selector import select_sound
        sound_selections = [select_sound(h) for h in highlights]

        self.update_state(state="PROGRESS", meta={"step": "placing_sounds"})
        from backend.placement.placer import create_placements
        placements = create_placements(highlights, sound_selections)

        self.update_state(state="PROGRESS", meta={"step": "rendering"})
        from backend.render.renderer import render_video
        output_path = f"{settings.outputs_dir}/{job_id}.mp4"
        Path(settings.outputs_dir).mkdir(parents=True, exist_ok=True)
        render_video(video_path, placements, output_path)

        shutil.rmtree(work_dir, ignore_errors=True)
        return {"status": "done", "output": output_path, "sounds_added": len(placements)}

    except Exception as e:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise
```

- [ ] **Step 2: Commit**

```bash
git add tasks.py
git commit -m "feat: Celery pipeline task orchestration"
```

---

## Task 15: FastAPI Backend

**Files:**
- Create: `backend/main.py`

- [ ] **Step 1: Create `backend/main.py`**

```python
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uuid, shutil
from backend.config import settings
from tasks import process_video

app = FastAPI(title="Meme Sound Inserter")
app.mount("/static", StaticFiles(directory="frontend"), name="static")

Path(settings.uploads_dir).mkdir(parents=True, exist_ok=True)
Path(settings.outputs_dir).mkdir(parents=True, exist_ok=True)

@app.get("/")
def index():
    return FileResponse("frontend/index.html")

@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    if not file.content_type.startswith("video/"):
        raise HTTPException(400, "File must be a video")

    job_id = str(uuid.uuid4())
    video_path = f"{settings.uploads_dir}/{job_id}_{file.filename}"

    with open(video_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    task = process_video.delay(video_path, job_id)
    return {"job_id": job_id, "task_id": task.id}

@app.get("/status/{task_id}")
def get_status(task_id: str):
    from celery.result import AsyncResult
    from tasks import app as celery_app
    result = AsyncResult(task_id, app=celery_app)
    response = {"status": result.status}
    if result.status == "PROGRESS":
        response["step"] = result.info.get("step", "")
    elif result.status == "SUCCESS":
        response["result"] = result.result
    elif result.status == "FAILURE":
        response["error"] = str(result.result)
    return JSONResponse(response)

@app.get("/download/{job_id}")
def download_video(job_id: str):
    path = f"{settings.outputs_dir}/{job_id}.mp4"
    if not Path(path).exists():
        raise HTTPException(404, "Video not found or not ready")
    return FileResponse(path, media_type="video/mp4", filename=f"meme_{job_id[:8]}.mp4")
```

- [ ] **Step 2: Commit**

```bash
git add backend/main.py
git commit -m "feat: FastAPI backend (upload/status/download)"
```

---

## Task 16: Frontend UI

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/style.css`
- Create: `frontend/app.js`

- [ ] **Step 1: Create `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Meme Sound Inserter</title>
  <meta name="description" content="Tự động chèn meme sound effects vào video của bạn">
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <div class="container">
    <h1>🎵 Meme Sound Inserter</h1>
    <p class="subtitle">Upload video — AI tự động chèn meme sounds vào các khoảnh khắc phù hợp</p>

    <div class="upload-zone" id="uploadZone">
      <div class="upload-icon">📹</div>
      <p>Kéo thả video vào đây hoặc <label for="fileInput" class="link">chọn file</label></p>
      <p class="hint">Hỗ trợ MP4, MOV, WebM — tối đa 500MB, dưới 3 phút</p>
      <input type="file" id="fileInput" accept="video/*" hidden>
    </div>

    <div class="status-section" id="statusSection" style="display:none">
      <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
      <p class="status-text" id="statusText">Đang xử lý...</p>
    </div>

    <div class="result-section" id="resultSection" style="display:none">
      <p class="success">✅ Hoàn thành! Video đã được chèn meme sounds.</p>
      <a class="download-btn" id="downloadBtn" href="#">⬇️ Tải Video</a>
    </div>

    <div class="error-section" id="errorSection" style="display:none">
      <p class="error" id="errorText"></p>
    </div>
  </div>
  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create `frontend/style.css`**

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: 'Inter', sans-serif;
  background: #0f0f13;
  color: #e0e0e0;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

.container {
  width: 100%;
  max-width: 600px;
  padding: 2rem;
  text-align: center;
}

h1 { font-size: 2rem; font-weight: 700; margin-bottom: 0.5rem; color: #fff; }
.subtitle { color: #888; margin-bottom: 2rem; line-height: 1.5; }

.upload-zone {
  border: 2px dashed #333;
  border-radius: 16px;
  padding: 3rem 2rem;
  cursor: pointer;
  transition: border-color 0.2s, background 0.2s;
}
.upload-zone:hover, .upload-zone.dragover {
  border-color: #7c3aed;
  background: rgba(124,58,237,0.05);
}
.upload-icon { font-size: 3rem; margin-bottom: 1rem; }
.link { color: #7c3aed; cursor: pointer; text-decoration: underline; }
.hint { color: #555; font-size: 0.85rem; margin-top: 0.5rem; }

.status-section { margin-top: 2rem; }
.progress-bar {
  height: 6px;
  background: #222;
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 1rem;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #7c3aed, #a855f7);
  border-radius: 3px;
  animation: pulse 1.5s ease-in-out infinite;
  width: 60%;
}
@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.6; } }
.status-text { color: #aaa; }

.result-section { margin-top: 2rem; }
.success { color: #4ade80; margin-bottom: 1.5rem; }
.download-btn {
  display: inline-block;
  padding: 0.875rem 2rem;
  background: linear-gradient(135deg, #7c3aed, #a855f7);
  color: white;
  text-decoration: none;
  border-radius: 12px;
  font-weight: 600;
  transition: transform 0.15s, box-shadow 0.15s;
}
.download-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(124,58,237,0.4);
}

.error { color: #f87171; margin-top: 1.5rem; }
```

- [ ] **Step 3: Create `frontend/app.js`**

```javascript
const uploadZone = document.getElementById('uploadZone');
const fileInput = document.getElementById('fileInput');
const statusSection = document.getElementById('statusSection');
const statusText = document.getElementById('statusText');
const resultSection = document.getElementById('resultSection');
const downloadBtn = document.getElementById('downloadBtn');
const errorSection = document.getElementById('errorSection');
const errorText = document.getElementById('errorText');

const STEP_LABELS = {
  extracting: '🎬 Đang trích xuất audio và frames...',
  transcribing: '🎤 Đang nhận dạng giọng nói...',
  analyzing_signals: '📊 Đang phân tích tín hiệu...',
  detecting_highlights: '🔍 Đang phát hiện highlight...',
  selecting_sounds: '🎵 Đang chọn meme sounds...',
  placing_sounds: '⏱️ Đang xác định thời điểm chèn...',
  rendering: '🎞️ Đang render video...',
};

uploadZone.addEventListener('dragover', e => {
  e.preventDefault();
  uploadZone.classList.add('dragover');
});
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
uploadZone.addEventListener('drop', e => {
  e.preventDefault();
  uploadZone.classList.remove('dragover');
  if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
});
uploadZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) handleFile(fileInput.files[0]);
});

async function handleFile(file) {
  uploadZone.style.display = 'none';
  statusSection.style.display = 'block';
  errorSection.style.display = 'none';
  resultSection.style.display = 'none';
  statusText.textContent = '⬆️ Đang upload...';

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/upload', { method: 'POST', body: formData });
    if (!res.ok) throw new Error(await res.text());
    const { task_id, job_id } = await res.json();
    pollStatus(task_id, job_id);
  } catch (err) {
    showError(err.message);
  }
}

async function pollStatus(taskId, jobId) {
  const interval = setInterval(async () => {
    try {
      const res = await fetch(`/status/${taskId}`);
      const data = await res.json();

      if (data.status === 'PROGRESS') {
        statusText.textContent = STEP_LABELS[data.step] || '⚙️ Đang xử lý...';
      } else if (data.status === 'SUCCESS') {
        clearInterval(interval);
        statusSection.style.display = 'none';
        resultSection.style.display = 'block';
        downloadBtn.href = `/download/${jobId}`;
      } else if (data.status === 'FAILURE') {
        clearInterval(interval);
        showError(data.error || 'Có lỗi xảy ra');
      }
    } catch (err) {
      clearInterval(interval);
      showError(err.message);
    }
  }, 2000);
}

function showError(msg) {
  statusSection.style.display = 'none';
  uploadZone.style.display = 'block';
  errorSection.style.display = 'block';
  errorText.textContent = `❌ Lỗi: ${msg}`;
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/
git commit -m "feat: frontend UI (upload, status polling, download)"
```

---

## Task 17: README + Run Instructions

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create `README.md`**

```markdown
# Meme Sound Inserter

Tự động chèn meme sound effects vào video short-form.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Điền OPENROUTER_API_KEY vào .env
```

## Chạy Redis

```bash
docker compose up -d
```

## Seed sound library

```bash
python scripts/seed_sounds.py --pages 5
```

## Start services

```bash
# Terminal 1: Backend
uvicorn backend.main:app --reload

# Terminal 2: Celery worker
celery -A tasks worker --loglevel=info
```

Mở http://localhost:8000

## Run tests

```bash
pytest tests/ -v
```
```

- [ ] **Step 2: Final commit**

```bash
git add README.md
git commit -m "docs: README with setup instructions"
```

---

## Task 18: Integration Test

- [ ] **Step 1: Install dependencies and run all tests**

```bash
pip install -r requirements.txt
pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 2: Seed 1 page of sounds (smoke test)**

```bash
python scripts/seed_sounds.py --pages 1
```

Expected: 20-30 sounds added to DB

- [ ] **Step 3: Start services and do manual end-to-end test**

```bash
# Terminal 1
docker compose up -d
uvicorn backend.main:app --reload

# Terminal 2
celery -A tasks worker --loglevel=info
```

Open http://localhost:8000, upload a short test video, verify:
- Status updates step by step
- Output video downloads successfully
- At least 1 meme sound audible in output

---

## Summary

| Task | Component | Est. |
|---|---|---|
| 1 | Scaffolding | 1h |
| 2 | Database | 1h |
| 3 | Crawler | 2h |
| 4 | Tagger | 1h |
| 5 | Sound Library | 1h |
| 6 | Video Ingestion | 2h |
| 7 | Transcript Signal | 2h |
| 8 | Audio/Visual/Face Signals | 3h |
| 9 | Highlight Detector | 3h |
| 10 | LLM Validator | 1h |
| 11 | Sound Selector | 2h |
| 12 | Timeline Placer | 2h |
| 13 | Renderer | 2h |
| 14 | Celery Orchestration | 2h |
| 15 | FastAPI Backend | 2h |
| 16 | Frontend | 3h |
| 17 | README | 0.5h |
| 18 | Integration Test | 2h |
| **Total** | | **~32h (4 ngày thực)** |
