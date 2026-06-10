from backend.detection.density import apply_density_cap, max_major_sounds
from backend.detection.highlight_detector import Highlight


def test_max_major_sounds_60s():
    assert max_major_sounds(60.0) == 12


def test_density_cap_keeps_top_impact():
    highlights = [
        Highlight(0, 1000, 500, 0.9, impact_score=100, sfx_tier="comedy"),
        Highlight(2000, 3000, 2500, 0.8, impact_score=50, sfx_tier="emphasis"),
        Highlight(4000, 5000, 4500, 0.7, impact_score=30, sfx_tier="emphasis"),
    ]
    capped = apply_density_cap(highlights, video_duration_sec=10.0)
    assert len(capped) == 2
    assert capped[0].impact_score == 100
