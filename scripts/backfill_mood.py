"""
Backfill mood column for background-tier sounds.
Usage: python scripts/backfill_mood.py
"""
import sys

sys.path.insert(0, ".")

import sqlite3

from backend.config import settings
from backend.db.models import get_sounds, init_db
from backend.sound.tagger import tag_sound

MOOD_PROMPT_SUFFIX = (
    'Also include "mood": "chill|dramatic|hype|ambient" for background ambient tracks.'
)


def infer_mood_from_tags(tag_data: dict) -> str:
    emotion = (tag_data.get("emotion") or "").lower()
    if emotion in {"shock", "fail", "awkward", "dramatic"}:
        return "dramatic"
    if emotion in {"hype", "funny", "win"}:
        return "hype"
    return tag_data.get("mood") or "chill"


def main():
    init_db(settings.db_path)
    sounds = get_sounds(settings.db_path)
    targets = [
        s for s in sounds
        if (s.get("tier") or "") == "background" and not s.get("mood")
    ]
    if not targets:
        print("No background sounds need mood backfill")
        return

    conn = sqlite3.connect(settings.db_path)
    updated = 0
    for sound in targets:
        try:
            tag_data = tag_sound(sound["name"], int(sound.get("duration_ms") or 1000))
            mood = infer_mood_from_tags(tag_data)
        except Exception as exc:
            print(f"Skip {sound['name']}: {exc}")
            mood = "chill"
        conn.execute("UPDATE sounds SET mood = ? WHERE id = ?", (mood, sound["id"]))
        updated += 1
        print(f"  {sound['name']} -> mood={mood}")

    conn.commit()
    conn.close()
    print(f"Backfilled mood for {updated} background sounds")


if __name__ == "__main__":
    main()
