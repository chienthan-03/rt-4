import json
import sqlite3
from pathlib import Path
from typing import Optional

def init_db(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sounds (
            id            TEXT PRIMARY KEY,
            name          TEXT NOT NULL,
            source_url    TEXT,
            file_path     TEXT NOT NULL,
            duration_ms   INTEGER,
            emotion       TEXT,
            mood          TEXT,
            intensity     REAL,
            timing_type   TEXT,
            tier          TEXT DEFAULT 'emphasis',
            tags          TEXT,
            event_types   TEXT,
            description   TEXT,
            use_count     INTEGER DEFAULT 0,
            accept_rate   REAL DEFAULT 0.0,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    try:
        conn.execute("ALTER TABLE sounds ADD COLUMN tier TEXT DEFAULT 'emphasis'")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE sounds ADD COLUMN mood TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

def insert_sound(db_path: str, sound: dict):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        INSERT OR REPLACE INTO sounds
        (id, name, source_url, file_path, duration_ms, emotion, mood, intensity,
         timing_type, tier, tags, event_types, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        sound["id"], sound["name"], sound.get("source_url"),
        sound["file_path"], sound.get("duration_ms"),
        sound.get("emotion"), sound.get("mood"), sound.get("intensity"), sound.get("timing_type"),
        sound.get("tier") or "emphasis",
        json.dumps(sound.get("tags", [])),
        json.dumps(sound.get("event_types", [])),
        sound.get("description")
    ))
    conn.commit()
    conn.close()

def get_sounds(db_path: str) -> list[dict]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM sounds").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def find_sound_by_name(db_path: str, name: str) -> Optional[dict]:
    sounds = get_sounds(db_path)
    if not sounds:
        return None

    needle = name.lower().replace("_", " ").replace("-", " ")
    for sound in sounds:
        haystack = f"{sound['name']} {Path(sound['file_path']).stem}".lower()
        haystack = haystack.replace("_", " ").replace("-", " ")
        if needle in haystack:
            return sound

    return sounds[0]

def update_sound_stats(db_path: str, sound_id: str, accepted: bool):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        UPDATE sounds SET
            use_count = use_count + 1,
            accept_rate = (accept_rate * use_count + ?) / (use_count + 1)
        WHERE id = ?
    """, (1.0 if accepted else 0.0, sound_id))
    conn.commit()
    conn.close()
