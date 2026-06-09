# Meme Sound Inserter

Tự động chèn meme sound effects vào video short-form bằng AI.

## Cách hoạt động

1. Upload video (MP4/MOV/WebM, tối đa 3 phút)
2. AI phân tích audio, transcript, facial expressions
3. Phát hiện các khoảnh khắc phù hợp để chèn sound
4. Chọn meme sound phù hợp nhất qua ChromaDB + Gemini Flash
5. Render video đầu ra với meme sounds đã được chèn

## Setup

```bash
# 1. Clone và tạo virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows

# 2. Cài dependencies
pip install -r requirements.txt

# 3. Cấu hình API key
cp .env.example .env
# Mở .env và điền OPENROUTER_API_KEY
```

## Chạy Redis

```bash
docker compose up -d
```

## Seed sound library (lần đầu)

```bash
python scripts/seed_sounds.py --pages 5
```

## Start services

```bash
# Terminal 1 — FastAPI backend
uvicorn backend.main:app --reload

# Terminal 2 — Celery worker
celery -A tasks worker --loglevel=info --pool=solo
```

Mở http://localhost:8000

## Run tests

```bash
python -m pytest tests/ -v
```

## Tech Stack

| Layer | Tool |
|---|---|
| Frontend | HTML + Vanilla JS |
| Backend | FastAPI + Celery + Redis |
| ASR | Whisper via OpenRouter |
| LLM | Gemini Flash via OpenRouter |
| Audio analysis | librosa |
| Face detection | mediapipe |
| Vector DB | ChromaDB |
| Metadata DB | SQLite |
| Render | ffmpeg |

## Chi phí ước tính

~$0.011/video (dưới 3 phút)
- Whisper: ~$0.009
- Gemini Flash (2 calls): ~$0.002
