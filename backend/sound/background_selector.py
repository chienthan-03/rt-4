# backend/sound/background_selector.py
import random
from pathlib import Path

from backend.config import settings
from backend.db.models import get_sounds, init_db
from backend.sound.library import sound_to_selection


def _background_pool(db_path: str | None = None) -> list[dict]:
    db_path = db_path or settings.db_path
    init_db(db_path)
    return [s for s in get_sounds(db_path) if (s.get("tier") or "") == "background"]


def _pick_for_mood(
    pool: list[dict],
    mood: str,
    exclude_ids: set[str],
) -> dict | None:
    mood_matches = [s for s in pool if (s.get("mood") or "chill") == mood]
    candidates = mood_matches or pool
    non_repeat = [s for s in candidates if s["id"] not in exclude_ids]
    if non_repeat:
        candidates = non_repeat
    if not candidates:
        return None
    return random.choice(candidates)


def select_background_for_segments(
    segments: list[dict],
    db_path: str | None = None,
) -> list[dict]:
    pool = _background_pool(db_path)
    if not pool:
        return []

    results: list[dict] = []
    last_id: str | None = None

    for seg in segments:
        sound = _pick_for_mood(pool, seg.get("mood", "chill"), exclude_ids={last_id} if last_id else set())
        if not sound:
            continue
        file_path = sound.get("file_path", "")
        if not file_path or not Path(file_path).is_file():
            continue
        selection = sound_to_selection(sound, reason="background_mood")
        results.append({
            **seg,
            "sound_file": file_path,
            "sound_id": sound["id"],
            "selection": selection,
        })
        last_id = sound["id"]

    return results
