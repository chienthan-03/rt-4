from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Prefer project .env over stale shell/user OPENROUTER_API_KEY (common on Windows).
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

class Settings(BaseSettings):
    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    whisper_model: str = "openai/whisper-1"
    llm_model: str = "google/gemini-2.5-flash"
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
