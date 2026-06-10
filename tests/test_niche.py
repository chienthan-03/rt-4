import pytest

from backend.detection.density import max_major_sounds
from backend.detection.minor_density import max_minor_per_window, plan_minor_density
from backend.detection.minor_cues import MinorCue
from backend.detection.niche import normalize_niche


def test_normalize_niche_defaults():
    assert normalize_niche(None) == "entertainment"
    assert normalize_niche("") == "entertainment"


def test_normalize_niche_valid():
    assert normalize_niche("edu") == "edu"
    assert normalize_niche("  Lifestyle ") == "lifestyle"


def test_normalize_niche_invalid():
    with pytest.raises(ValueError):
        normalize_niche("gaming")


def test_niche_density_presets():
    assert max_major_sounds(40.0, "entertainment") == 8
    assert max_major_sounds(40.0, "edu") == 5
    assert max_major_sounds(40.0, "lifestyle") == 4
    assert max_minor_per_window("entertainment") == 2
    assert max_minor_per_window("edu") == 0
    assert max_minor_per_window("lifestyle") == 1


def test_plan_minor_density_respects_niche():
    cues = [MinorCue(timestamp_ms=i * 400, score=float(i)) for i in range(1, 8)]
    edu_kept = plan_minor_density(cues, video_duration_sec=10.0, niche="edu")
    assert len(edu_kept) == 0
    entertainment_kept = plan_minor_density(cues, video_duration_sec=10.0, niche="entertainment")
    assert len(entertainment_kept) == 2
