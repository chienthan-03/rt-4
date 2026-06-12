# tests/test_background_placements.py
from pathlib import Path
from unittest.mock import patch

from backend.placement.placer import create_background_placements

MAJOR_DIP_MS = 500


@patch.object(Path, "is_file", return_value=True)
def test_full_span_placement(mock_is_file):
    selections = [
        {
            "start_ms": 0,
            "end_ms": 30000,
            "mood": "chill",
            "sound_file": "/bg/chill.mp3",
        }
    ]
    placements = create_background_placements(selections, major_placements=[], duration_ms=30000)
    assert len(placements) == 1
    assert placements[0]["start_ms"] == 0
    assert placements[0]["end_ms"] == 30000
    assert placements[0]["fade_in_ms"] == 500
    assert placements[0]["fade_out_ms"] == 1000
    assert placements[0]["track"] == "background"


@patch.object(Path, "is_file", return_value=True)
def test_splits_before_major(mock_is_file):
    selections = [
        {"start_ms": 0, "end_ms": 20000, "mood": "chill", "sound_file": "/bg/chill.mp3"},
    ]
    major = [{"insert_ms": 10000, "end_ms": 11000}]
    placements = create_background_placements(
        selections, major_placements=major, duration_ms=20000, major_dip_ms=MAJOR_DIP_MS
    )
    assert len(placements) >= 2
    assert all(p["end_ms"] <= 10000 - MAJOR_DIP_MS or p["start_ms"] >= 11000 for p in placements)
