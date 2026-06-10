from unittest.mock import patch, MagicMock
from backend.detection.highlight_detector import Highlight
from backend.sound.selector import (
    apply_fallback_rule,
    build_search_query,
    select_sounds,
    _filter_fresh_candidates,
)

def test_build_search_query():
    from backend.detection.highlight_detector import Highlight
    h = Highlight(0, 1000, 500, 0.8, "fail", "shock", 0.8, ["audio_spike"], "oh no")
    q = build_search_query(h)
    assert "fail" in q
    assert "shock" in q

def test_fallback_rule_returns_resolved_sound():
    result = apply_fallback_rule("shock")
    assert result is not None
    assert result.get("chosen_id")
    assert result["metadata"].get("file_path")
    assert "vine" in result["metadata"]["file_path"].lower()

def test_filter_fresh_candidates_prefers_unused():
    candidates = [
        {"id": "a", "metadata": {"name": "vine_boom"}},
        {"id": "b", "metadata": {"name": "bruh"}},
    ]
    fresh = _filter_fresh_candidates(candidates, {"a"})
    assert len(fresh) == 1
    assert fresh[0]["id"] == "b"

def test_filter_fresh_candidates_allows_reuse_when_exhausted():
    candidates = [{"id": "a", "metadata": {"name": "vine_boom"}}]
    fresh = _filter_fresh_candidates(candidates, {"a"})
    assert fresh == candidates

def test_select_sounds_avoids_repeats():
    highlights = [
        Highlight(0, 1000, 500, 0.8, "fail", "shock", 0.8, [], "oh no"),
        Highlight(2000, 3000, 2500, 0.7, "fail", "shock", 0.7, [], "bruh"),
    ]
    candidates = [
        {"id": "sound-a", "metadata": {"name": "vine_boom", "emotion": "shock"}},
        {"id": "sound-b", "metadata": {"name": "metal_pipe", "emotion": "fail"}},
    ]

    with patch("backend.sound.selector.search_sounds", return_value=candidates):
        with patch("backend.sound.selector.llm_rerank") as mock_rerank:
            mock_rerank.side_effect = [
                {"chosen_id": "sound-a", "reason": "first"},
                {"chosen_id": "sound-a", "reason": "repeat"},
            ]
            selections = select_sounds(highlights)

    assert selections[0]["chosen_id"] == "sound-a"
    assert selections[1]["chosen_id"] == "sound-b"
