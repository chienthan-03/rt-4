"""
Usage: python scripts/seed_sounds.py --pages 5
Crawls MyInstants, downloads sounds, tags them, stores in DB.
"""
import argparse
import sys
sys.path.insert(0, ".")

from backend.sound.crawler import crawl_myinstants, download_mp3
from backend.sound.tagger import tag_sound
from backend.sound.library import add_sound_to_library
from backend.config import settings
from pathlib import Path
import time

def main(max_pages: int):
    print(f"Crawling MyInstants (max {max_pages} pages)...")
    sounds = crawl_myinstants(max_pages=max_pages)
    print(f"Found {len(sounds)} sounds")

    for i, s in enumerate(sounds):
        try:
            filename = Path(s["mp3_url"]).name
            file_path = download_mp3(s["mp3_url"], settings.sounds_dir, filename)
            from backend.sound.library import get_audio_duration_ms
            real_duration_ms = get_audio_duration_ms(file_path)  # use real duration
            tags = tag_sound(s["name"], duration_ms=real_duration_ms)
            sound_id = add_sound_to_library(s["name"], file_path, s["source_url"], tags)
            print(f"[{i+1}/{len(sounds)}] Added: {s['name']} ({sound_id[:8]}...)")
            time.sleep(0.5)
        except Exception as e:
            print(f"[{i+1}/{len(sounds)}] SKIP {s['name']}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=5)
    args = parser.parse_args()
    main(args.pages)
