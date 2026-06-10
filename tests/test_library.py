def test_build_chroma_document_contains_all_fields():
    from backend.sound.library import build_chroma_document
    sound = {
        "description": "Short boom",
        "tags": ["impact", "meme"],
        "emotion": "shock",
        "event_types": ["fall", "fail"]
    }
    doc = build_chroma_document(sound)
    assert "Short boom" in doc
    assert "impact" in doc
    assert "shock" in doc
    assert "fall" in doc

def test_build_chroma_document_handles_missing_fields():
    from backend.sound.library import build_chroma_document
    doc = build_chroma_document({})  # no fields — must not raise
    assert isinstance(doc, str)

def test_find_sound_by_alias_matches_filename():
    from backend.sound.library import find_sound_by_alias
    sound = find_sound_by_alias("vine-boom")
    assert sound is not None
    assert "vine-boom" in sound["file_path"].lower()

def test_resolve_fallback_sound_for_shock():
    from backend.sound.library import resolve_fallback_sound
    sound = resolve_fallback_sound("shock")
    assert sound is not None
    assert sound.get("file_path")
