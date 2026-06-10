"""
Index existing MP3 files in sounds/ into SQLite + ChromaDB.

Usage: python scripts/index_local_sounds.py
"""
import sys

sys.path.insert(0, ".")

from pathlib import Path

from backend.config import settings
from backend.db.models import get_sounds, init_db
from backend.sound.library import add_sound_to_library


def default_tags(name: str, duration_ms: int) -> dict:
    slug = name.lower()
    emotion = "funny"
    if any(k in slug for k in ("sad", "violin", "dram")):
        emotion = "dramatic"
    elif any(k in slug for k in ("boom", "vine", "shock", "wow")):
        emotion = "shock"
    elif any(k in slug for k in ("bruh", "awkward")):
        emotion = "awkward"
    elif any(k in slug for k in ("fail", "pipe", "crack")):
        emotion = "fail"
    elif any(k in slug for k in ("cheer", "hype", "win")):
        emotion = "hype"

    timing_type = "instant" if duration_ms < 2000 else "reaction"
    return {
        "emotion": emotion,
        "intensity": 0.6,
        "timing_type": timing_type,
        "tags": [name.replace("-", " ").replace("_", " ")],
        "event_types": ["general"],
        "description": f"Meme sound effect: {name}",
    }


def main() -> None:
    init_db(settings.db_path)
    sounds_dir = Path(settings.sounds_dir)
    if not sounds_dir.is_dir():
        raise SystemExit(f"Sounds directory not found: {sounds_dir}")

    indexed_paths = {
        str(Path(s["file_path"]).resolve())
        for s in get_sounds(settings.db_path)
        if s.get("file_path")
    }
    mp3_files = sorted(sounds_dir.glob("*.mp3"))

    added = 0
    skipped = 0
    for mp3 in mp3_files:
        resolved = str(mp3.resolve())
        if resolved in indexed_paths:
            skipped += 1
            continue

        from backend.sound.library import get_audio_duration_ms

        duration_ms = get_audio_duration_ms(str(mp3))
        name = mp3.stem.replace("-", " ").replace("_", " ")
        tags = default_tags(mp3.stem, duration_ms)
        add_sound_to_library(name, str(mp3), source_url="", tag_data=tags)
        added += 1
        print(f"Indexed: {mp3.name}")

    print(f"Done. Added {added}, skipped {skipped} (already indexed), total files {len(mp3_files)}")


if __name__ == "__main__":
    main()
