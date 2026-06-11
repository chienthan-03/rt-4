"""Select Tier background ambient sounds by mood (no LLM)."""

from backend.config import settings
from backend.db.models import get_sounds, init_db
from backend.sound.library import sound_to_selection


def _background_pool(db_path: str | None = None) -> list[dict]:
    db_path = db_path or settings.db_path
    init_db(db_path)
    return [s for s in get_sounds(db_path) if (s.get("tier") or "") == "background"]


def select_background_sound(mood: str = "chill", db_path: str | None = None) -> dict | None:
    pool = _background_pool(db_path)
    if not pool:
        return None

    mood_matches = [s for s in pool if (s.get("mood") or "chill") == mood]
    candidates = mood_matches or pool
    return sound_to_selection(candidates[0], reason="background_mood")
