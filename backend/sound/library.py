import re
import uuid
import librosa
from pathlib import Path
from backend.db.models import init_db, insert_sound, get_sounds
from backend.db.chroma import add_sound_embedding
from backend.config import settings

FALLBACK_ALIASES: dict[str, list[str]] = {
    "shock": ["vine-boom", "vine boom", "shocked"],
    "fail": ["punch", "bone-crack", "bone crack"],
    "sadness": ["tf_nemesis", "sad violin"],
    "hype": ["10-diem", "ghe-chua", "anime-wow"],
    "awkward": ["bruh", "huh", "mac quack"],
    "dramatic": ["dun-dun", "dramatic", "tf_nemesis"],
    "funny": ["baby-laughing", "thay-giao-ba-cuoi", "hahaha"],
}

def get_audio_duration_ms(file_path: str) -> int:
    y, sr = librosa.load(file_path, sr=None, mono=True)
    return int(len(y) / sr * 1000)

def _normalize_sound_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def find_sound_by_alias(alias: str, db_path: str | None = None) -> dict | None:
    """Find a library sound whose name or filename matches an alias."""
    db_path = db_path or settings.db_path
    init_db(db_path)
    needle = _normalize_sound_key(alias)
    if not needle:
        return None

    for sound in get_sounds(db_path):
        haystacks = [
            sound.get("name") or "",
            Path(sound.get("file_path") or "").stem,
        ]
        for haystack in haystacks:
            if needle in _normalize_sound_key(haystack):
                return sound
    return None


def resolve_fallback_sound(emotion: str, db_path: str | None = None) -> dict | None:
    """Resolve emotion-based fallback to a concrete library sound."""
    for alias in FALLBACK_ALIASES.get(emotion, []):
        sound = find_sound_by_alias(alias, db_path=db_path)
        if sound:
            return sound
    return None


def sound_to_selection(sound: dict, reason: str = "fallback") -> dict:
    return {
        "chosen_id": sound["id"],
        "metadata": {
            "name": sound.get("name"),
            "emotion": sound.get("emotion"),
            "mood": sound.get("mood"),
            "intensity": float(sound.get("intensity") or 0.5),
            "timing_type": sound.get("timing_type") or "instant",
            "tier": sound.get("tier") or "emphasis",
            "file_path": sound.get("file_path"),
            "duration_ms": sound.get("duration_ms"),
        },
        "reason": reason,
    }


def build_chroma_document(sound: dict) -> str:
    tags = ", ".join(sound.get("tags") or [])
    events = ", ".join(sound.get("event_types") or [])
    return (
        f"{sound.get('description') or ''}. "
        f"Tags: {tags}. Emotion: {sound.get('emotion') or ''}. Mood: {sound.get('mood') or ''}. "
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
        "mood": tag_data.get("mood") or "",
        "intensity": float(tag_data.get("intensity") or 0.5),
        "timing_type": tag_data.get("timing_type") or "instant",
        "tier": tag_data.get("tier") or "emphasis",
        "name": name,
        "file_path": file_path,
        "duration_ms": duration_ms,
    })
    return sound_id
