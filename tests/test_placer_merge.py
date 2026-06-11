import pytest

from backend.detection.minor_cues import MinorCue
from backend.placement.placer import create_minor_placements, merge_placements


def test_merge_placements_major_wins_overlap():
    major = [{
        "sound_file": "major.mp3",
        "insert_ms": 2000,
        "end_ms": 3000,
        "volume": 0.5,
        "fade_out_ms": 50,
        "confidence": 80,
    }]
    minor = [{
        "sound_file": "minor.mp3",
        "insert_ms": 2100,
        "end_ms": 2500,
        "volume": 0.25,
        "fade_out_ms": 30,
        "confidence": 0.5,
        "track": "minor",
    }]
    merged = merge_placements(major, minor)
    assert len(merged) == 1
    assert merged[0]["track"] == "major"


def test_create_minor_placements_lower_volume():
    cues = [MinorCue(timestamp_ms=1000, score=0.5)]
    selections = [{
        "chosen_id": "x",
        "metadata": {
            "file_path": __file__,
            "duration_ms": 500,
        },
    }]
    placements = create_minor_placements(cues, selections, minor_volume=0.35)
    assert len(placements) == 1
    assert placements[0]["volume"] == pytest.approx(0.35)
