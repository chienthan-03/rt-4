"""
Backfill tier column on existing sounds.
Usage: python scripts/backfill_tiers.py
"""
import json
import sys

sys.path.insert(0, ".")

from backend.config import settings
from backend.db.models import get_sounds, init_db
import sqlite3

COMEDY_EMOTIONS = {"funny", "cringe", "awkward", "fail"}


def infer_tier(sound: dict) -> str:
    if sound.get("tier") in ("emphasis", "comedy"):
        return sound["tier"]
    emotion = (sound.get("emotion") or "").lower()
    if emotion in COMEDY_EMOTIONS:
        return "comedy"
    tags_raw = sound.get("tags") or "[]"
    try:
        tags = json.loads(tags_raw) if isinstance(tags_raw, str) else tags_raw
    except json.JSONDecodeError:
        tags = []
    comedy_tags = {"funny", "cringe", "awkward", "bruh", "laugh", "meme"}
    if any(t.lower() in comedy_tags for t in tags):
        return "comedy"
    return "emphasis"


def main():
    init_db(settings.db_path)
    sounds = get_sounds(settings.db_path)
    conn = sqlite3.connect(settings.db_path)
    updated = 0
    for sound in sounds:
        tier = infer_tier(sound)
        conn.execute("UPDATE sounds SET tier = ? WHERE id = ?", (tier, sound["id"]))
        updated += 1
    conn.commit()
    conn.close()
    print(f"Backfilled tier for {updated} sounds")


if __name__ == "__main__":
    main()
