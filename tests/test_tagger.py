from unittest.mock import patch

def test_build_tag_prompt():
    from backend.sound.tagger import build_tag_prompt
    prompt = build_tag_prompt("Vine Boom", 450)
    assert "Vine Boom" in prompt
    assert "450" in prompt
    assert "emotion" in prompt

def test_parse_tag_response():
    from backend.llm_json import parse_llm_json
    raw = '{"emotion": "shock", "intensity": 0.9, "timing_type": "instant", "tags": ["impact"], "event_types": ["fall"], "description": "short boom"}'
    result = parse_llm_json(raw)
    assert result["emotion"] == "shock"
    assert result["intensity"] == 0.9
