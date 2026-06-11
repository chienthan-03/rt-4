def test_sounds_table_created(tmp_path):
    from backend.db.models import init_db, get_sounds
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    sounds = get_sounds(db_path)
    assert sounds == []

def test_db_init_adds_mood_column(tmp_path):
    from backend.db.models import init_db, insert_sound, get_sounds
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    insert_sound(db_path, {
        "id": "1",
        "name": "test_mood",
        "file_path": "path.mp3",
        "mood": "funny"
    })
    sounds = get_sounds(db_path)
    assert len(sounds) == 1
    assert sounds[0]["mood"] == "funny"
