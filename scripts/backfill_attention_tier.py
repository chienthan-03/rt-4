"""
Tag whoosh/pop/click sounds as tier=attention.
Usage: python scripts/backfill_attention_tier.py
"""
import sys

sys.path.insert(0, ".")

from backend.config import settings
from backend.db.models import get_sounds, init_db
from backend.sound.attention_map import ATTENTION_KEYWORDS
import sqlite3


def is_attention_sound(sound: dict) -> bool:
    name = (sound.get("name") or "").lower()
    stem = (sound.get("file_path") or "").lower()
    haystack = f"{name} {stem}"
    return any(kw in haystack for kw in ATTENTION_KEYWORDS)


def main():
    init_db(settings.db_path)
    sounds = get_sounds(settings.db_path)
    conn = sqlite3.connect(settings.db_path)
    updated = 0
    for sound in sounds:
        if not is_attention_sound(sound):
            continue
        if sound.get("tier") == "attention":
            continue
        conn.execute("UPDATE sounds SET tier = ? WHERE id = ?", ("attention", sound["id"]))
        updated += 1
    conn.commit()
    conn.close()
    attention_count = sum(1 for s in sounds if is_attention_sound(s))
    print(f"Tagged {updated} sounds as attention (total attention-like: {attention_count})")


if __name__ == "__main__":
    main()
