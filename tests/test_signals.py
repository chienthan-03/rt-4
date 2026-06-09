from unittest.mock import patch, MagicMock

def test_parse_whisper_response():
    from backend.signals.transcript import parse_whisper_segments
    mock_response = {
        "segments": [
            {"start": 0.0, "end": 1.5, "text": "oh no"},
            {"start": 2.0, "end": 3.0, "text": "what happened"}
        ]
    }
    segments = parse_whisper_segments(mock_response)
    assert len(segments) == 2
    assert segments[0]["text"] == "oh no"
    assert segments[0]["start_ms"] == 0

def test_keyword_score():
    from backend.signals.transcript import keyword_score
    assert keyword_score("oh no oh no") > 0.5
    assert keyword_score("the weather is nice") == 0.0
