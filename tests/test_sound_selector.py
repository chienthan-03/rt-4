from unittest.mock import patch, MagicMock
from backend.sound.selector import build_search_query, apply_fallback_rule

def test_build_search_query():
    from backend.detection.highlight_detector import Highlight
    h = Highlight(0, 1000, 500, 0.8, "fail", "shock", 0.8, ["audio_spike"], "oh no")
    q = build_search_query(h)
    assert "fail" in q
    assert "shock" in q

def test_fallback_rule_returns_something():
    result = apply_fallback_rule("shock")
    assert result is not None
