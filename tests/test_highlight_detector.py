from backend.detection.highlight_detector import merge_events, score_to_highlight, detect_highlights

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

def test_score_to_highlight_assigns_emotion_from_signal():
    merged = merge_events([
        {"timestamp_ms": 1000, "score": 0.8, "type": "speech_keyword", "context_text": "oh no"},
    ])[0]
    highlight = score_to_highlight(merged)
    assert highlight.emotion == "shock"
    assert highlight.event_type == "shock"

def test_detect_highlights_filters_low_score():
    events = [
        {"timestamp_ms": 1000, "score": 0.3, "type": "scene_change", "context_text": ""},
        {"timestamp_ms": 5000, "score": 0.8, "type": "audio_spike", "context_text": ""},
    ]
    highlights = detect_highlights(events, threshold=0.5)
    assert len(highlights) == 1
    assert highlights[0].emotion == "shock"

def test_detect_highlights_threshold_035():
    events = [
        {"timestamp_ms": 1000, "score": 0.4, "type": "speech_keyword", "context_text": "hello"},
    ]
    highlights = detect_highlights(events)
    assert len(highlights) == 1
    assert highlights[0].score == 0.4
