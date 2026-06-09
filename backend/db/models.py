import sqlite3
import json
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
            intensity     REAL,
            timing_type   TEXT,
            tags          TEXT,
            event_types   TEXT,
            description   TEXT,
            use_count     INTEGER DEFAULT 0,
            accept_rate   REAL DEFAULT 0.0,
            created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def insert_sound(db_path: str, sound: dict):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        INSERT OR REPLACE INTO sounds
        (id, name, source_url, file_path, duration_ms, emotion, intensity,
         timing_type, tags, event_types, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        sound["id"], sound["name"], sound.get("source_url"),
        sound["file_path"], sound.get("duration_ms"),
        sound.get("emotion"), sound.get("intensity"), sound.get("timing_type"),
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
