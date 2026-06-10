def test_strip_plain_json():
    """Plain JSON response (no fences) should parse correctly."""
    from backend.llm_json import parse_llm_json
    raw = '[{"index": 0, "keep": true, "event_type": "fail", "emotion": "shock"}]'
    decisions = parse_llm_json(raw)
    assert decisions[0]["keep"] is True
    assert decisions[0]["event_type"] == "fail"

def test_strip_json_fence():
    """```json fence should be stripped before parsing."""
    from backend.llm_json import parse_llm_json
    raw = '```json\n[{"index": 0, "keep": false, "event_type": "generic", "emotion": "neutral"}]\n```'
    decisions = parse_llm_json(raw)
    assert decisions[0]["keep"] is False

def test_strip_plain_fence():
    """Plain ``` fence (no 'json' label) should also be stripped."""
    from backend.llm_json import parse_llm_json
    raw = '```\n[{"index": 0, "keep": true, "event_type": "shock", "emotion": "shock"}]\n```'
    decisions = parse_llm_json(raw)
    assert len(decisions) == 1


def test_validate_highlights_applies_impact_gate():
    from unittest.mock import MagicMock, patch

    from backend.detection.highlight_detector import Highlight
    from backend.detection.llm_validator import validate_highlights

    highlights = [
        Highlight(0, 1000, 500, 0.8, context_text="oh no"),
        Highlight(2000, 3000, 2500, 0.6, context_text="hello"),
    ]
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(
            message=MagicMock(
                content="""[
        {"index": 0, "keep": true, "importance": 5, "surprise": 5, "emotion_score": 5,
         "has_punchline": true, "audience_emotion": "shock", "event_type": "fail", "emotion": "shock"},
        {"index": 1, "keep": true, "importance": 1, "surprise": 1, "emotion_score": 1,
         "has_punchline": false, "audience_emotion": "neutral", "event_type": "generic", "emotion": "shock"}
    ]"""
            )
        )
    ]
    with patch("backend.detection.llm_validator.get_client") as mock_client:
        mock_client.return_value.chat.completions.create.return_value = mock_response
        result = validate_highlights(highlights)

    assert len(result) == 1
    assert result[0].impact_score == 125
    assert result[0].sfx_tier == "comedy"
