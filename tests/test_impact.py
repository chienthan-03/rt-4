from backend.detection.highlight_detector import Highlight
from backend.detection.impact import (
    apply_impact_fields,
    assign_sfx_tier,
    compute_impact_score,
    should_keep_highlight,
)


def test_highlight_has_impact_fields():
    h = Highlight(
        start_ms=0,
        end_ms=1000,
        peak_ms=500,
        score=0.8,
        importance=4,
        surprise=4,
        emotion_score=4,
        impact_score=64,
        has_punchline=True,
        sfx_tier="comedy",
    )
    assert h.impact_score == 64
    assert h.sfx_tier == "comedy"


def test_compute_impact_score():
    assert compute_impact_score(4, 4, 4) == 64


def test_assign_sfx_tier_comedy_requires_punchline():
    assert assign_sfx_tier(64, has_punchline=True) == "comedy"
    assert assign_sfx_tier(64, has_punchline=False) == "emphasis"


def test_should_keep_below_threshold():
    assert should_keep_highlight(25) is False
    assert should_keep_highlight(30) is True
    assert should_keep_highlight(100) is True


def test_apply_impact_fields_sets_tier():
    h = Highlight(start_ms=0, end_ms=1000, peak_ms=500, score=0.8)
    apply_impact_fields(h, 5, 5, 5, has_punchline=True, audience_emotion="shock")
    assert h.impact_score == 125
    assert h.sfx_tier == "comedy"
    assert h.audience_emotion == "shock"
