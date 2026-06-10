from backend.detection.highlight_detector import Highlight
from backend.detection.minor_cues import extract_minor_cues


def test_extract_minor_cues_skips_near_major():
    events = [
        {"timestamp_ms": 1000, "score": 0.5, "type": "scene_change"},
        {"timestamp_ms": 1500, "score": 0.6, "type": "scene_change"},
        {"timestamp_ms": 5000, "score": 0.7, "type": "scene_change"},
    ]
    major = [Highlight(start_ms=900, end_ms=1100, peak_ms=1000, score=0.9, impact_score=60)]
    cues = extract_minor_cues(events, major_highlights=major)
    assert len(cues) == 1
    assert cues[0].timestamp_ms == 5000


def test_extract_minor_cues_enforces_min_gap():
    events = [
        {"timestamp_ms": 1000, "score": 0.5, "type": "scene_change"},
        {"timestamp_ms": 1100, "score": 0.6, "type": "scene_change"},
        {"timestamp_ms": 4500, "score": 0.7, "type": "scene_change"},
    ]
    cues = extract_minor_cues(events)
    assert len(cues) == 2
    assert cues[0].timestamp_ms == 1000
    assert cues[1].timestamp_ms == 4500


def test_extract_minor_cues_filters_weak_scene_changes():
    events = [
        {"timestamp_ms": 1000, "score": 0.3, "type": "scene_change"},
        {"timestamp_ms": 5000, "score": 0.55, "type": "scene_change"},
    ]
    cues = extract_minor_cues(events)
    assert len(cues) == 1
    assert cues[0].timestamp_ms == 5000
