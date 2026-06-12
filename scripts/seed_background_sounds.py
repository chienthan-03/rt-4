"""Index sounds/background/*.mp3 with tier=background. Usage: python scripts/seed_background_sounds.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from backend.config import settings
from backend.db.models import get_sounds, init_db
from backend.sound.library import add_sound_to_library, get_audio_duration_ms

MANIFEST = Path(settings.sounds_dir) / "background" / "manifest.json"
BG_DIR = Path(settings.sounds_dir) / "background"


def main():
    init_db(settings.db_path)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.is_file() else []
    mood_by_file = {m["filename"]: m.get("mood", "chill") for m in manifest}

    indexed = {str(Path(s["file_path"]).resolve()) for s in get_sounds(settings.db_path)}
    added = 0

    for mp3 in sorted(BG_DIR.glob("*.mp3")):
        resolved = str(mp3.resolve())
        if resolved in indexed:
            print(f"SKIP {mp3.name}")
            continue
        duration_ms = get_audio_duration_ms(str(mp3))
        mood = mood_by_file.get(mp3.name, "chill")
        tag_data = {
            "tier": "background",
            "mood": mood,
            "emotion": mood,
            "intensity": 0.3,
            "timing_type": "buildup",
            "tags": ["background", mood, "ambient"],
            "event_types": ["ambient"],
            "description": f"Background ambient track ({mood})",
        }
        add_sound_to_library(mp3.stem, str(mp3), source_url="", tag_data=tag_data)
        added += 1
        print(f"Added {mp3.name} mood={mood}")

    print(f"Done. Added {added} background sounds.")


if __name__ == "__main__":
    main()
