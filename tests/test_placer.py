from backend.placement.placer import calculate_insert_ms, resolve_overlaps, create_placements
from backend.detection.highlight_detector import Highlight

def test_instant_timing():
    insert_ms = calculate_insert_ms(peak_ms=8500, sound_duration_ms=600, timing_type="instant")
    assert insert_ms == 8500 - int(600 * 0.1)

def test_reaction_timing():
    insert_ms = calculate_insert_ms(peak_ms=8500, sound_duration_ms=800, timing_type="reaction", end_ms=9000)
    assert insert_ms == 9000 + 200

def test_resolve_overlaps_keeps_higher_confidence():
    placements = [
        {"insert_ms": 1000, "end_ms": 1600, "confidence": 0.7, "sound_file": "a.mp3"},
        {"insert_ms": 1400, "end_ms": 2200, "confidence": 0.9, "sound_file": "b.mp3"},
    ]
    resolved = resolve_overlaps(placements)
    assert len(resolved) == 1
    assert resolved[0]["sound_file"] == "b.mp3"

def test_create_placements_custom_volume(tmp_path):
    sound_file = tmp_path / "test.mp3"
    sound_file.write_bytes(b"ID3")
    highlights = [Highlight(start_ms=1000, end_ms=2000, peak_ms=1500, score=0.8)]
    selections = [{
        "chosen_id": "sound1",
        "metadata": {
            "duration_ms": 1000,
            "timing_type": "instant",
            "file_path": str(sound_file),
        },
    }]
    placements = create_placements(highlights, selections, meme_volume=0.45)
    assert len(placements) == 1
    assert placements[0]["volume"] == 0.45


def test_create_placements_skips_missing_sound_file():
    highlights = [Highlight(start_ms=1000, end_ms=2000, peak_ms=1500, score=0.8)]
    selections = [{"chosen_id": "sound1", "metadata": {"duration_ms": 1000, "file_path": "missing.mp3"}}]
    placements = create_placements(highlights, selections)
    assert placements == []




def test_placements_no_double_offset(tmp_path):
    sound_file = tmp_path / "test.mp3"
    sound_file.write_bytes(b"ID3")
    h = Highlight(start_ms=0, end_ms=2000, peak_ms=1000, score=0.9, impact_score=64)
    sel = {
        "chosen_id": "x",
        "metadata": {
            "file_path": str(sound_file),
            "duration_ms": 1000,
            "timing_type": "instant",
        },
    }
    placements = create_placements([h], [sel])
    expected = calculate_insert_ms(1000, 1000, "instant")
    assert placements[0]["insert_ms"] == expected
