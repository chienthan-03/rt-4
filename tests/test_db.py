def test_sounds_table_created(tmp_path):
    from backend.db.models import init_db, get_sounds
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    sounds = get_sounds(db_path)
    assert sounds == []
