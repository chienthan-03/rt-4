def test_strip_plain_json():
    """Plain JSON response (no fences) should parse correctly."""
    from backend.detection.llm_validator import _parse_decisions
    raw = '[{"index": 0, "keep": true, "event_type": "fail", "emotion": "shock"}]'
    decisions = _parse_decisions(raw)
    assert decisions[0]["keep"] is True
    assert decisions[0]["event_type"] == "fail"

def test_strip_json_fence():
    """```json fence should be stripped before parsing."""
    from backend.detection.llm_validator import _parse_decisions
    raw = '```json\n[{"index": 0, "keep": false, "event_type": "generic", "emotion": "neutral"}]\n```'
    decisions = _parse_decisions(raw)
    assert decisions[0]["keep"] is False

def test_strip_plain_fence():
    """Plain ``` fence (no 'json' label) should also be stripped."""
    from backend.detection.llm_validator import _parse_decisions
    raw = '```\n[{"index": 0, "keep": true, "event_type": "shock", "emotion": "shock"}]\n```'
    decisions = _parse_decisions(raw)
    assert len(decisions) == 1
