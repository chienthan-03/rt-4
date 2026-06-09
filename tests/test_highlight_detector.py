from backend.detection.highlight_detector import merge_events, score_to_highlight

def test_merge_nearby_events():
    events = [
        {"timestamp_ms": 1000, "score": 0.6, "type": "audio_spike", "context_text": ""},
        {"timestamp_ms": 1500, "score": 0.7, "type": "speech_keyword", "context_text": "oh no"},
    ]
    merged = merge_events(events, window_ms=2000)
    assert len(merged) == 1
    assert merged[0]["score"] > 0.6

def test_far_events_not_merged():
    events = [
        {"timestamp_ms": 1000, "score": 0.6, "type": "audio_spike", "context_text": ""},
        {"timestamp_ms": 5000, "score": 0.7, "type": "speech_keyword", "context_text": "bruh"},
    ]
    merged = merge_events(events, window_ms=2000)
    assert len(merged) == 2
