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
    tags = ", ".join(sound.get("tags") or [])
    events = ", ".join(sound.get("event_types") or [])
    return (
        f"{sound.get('description') or ''}. "
        f"Tags: {tags}. Emotion: {sound.get('emotion') or ''}. "
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
        "emotion": tag_data.get("emotion") or "",
        "intensity": float(tag_data.get("intensity") or 0.5),
        "timing_type": tag_data.get("timing_type") or "instant",
        "name": name,
        "file_path": file_path,
        "duration_ms": duration_ms
    })
    return sound_id
