# tests/test_emotion_timeline.py
from backend.detection.emotion_timeline import (
    emotion_to_mood,
    build_emotion_timeline_rule,
    merge_short_segments,
)
from backend.detection.highlight_detector import Highlight


def test_emotion_to_mood_dramatic():
    assert emotion_to_mood(emotion="shock", audience_emotion="") == "dramatic"
    assert emotion_to_mood(emotion="", audience_emotion="cringe") == "dramatic"


def test_emotion_to_mood_hype():
    assert emotion_to_mood(emotion="funny", audience_emotion="") == "hype"


def test_emotion_to_mood_chill_fallback():
    assert emotion_to_mood(emotion="", audience_emotion="") == "chill"


def test_build_emotion_timeline_two_highlights():
    highlights = [
        Highlight(start_ms=0, end_ms=5000, peak_ms=4000, score=0.9, emotion="funny"),
        Highlight(start_ms=12000, end_ms=16000, peak_ms=14000, score=0.9, emotion="shock"),
    ]
    segments = build_emotion_timeline_rule(highlights, duration_ms=20000)
    assert segments[0]["start_ms"] == 0
    assert segments[-1]["end_ms"] == 20000
    assert any(s["mood"] == "hype" for s in segments)
    assert any(s["mood"] == "dramatic" for s in segments)


def test_merge_short_segments_merges_under_8s():
    segments = [
        {"start_ms": 0, "end_ms": 5000, "mood": "chill", "source": "rule"},
        {"start_ms": 5000, "end_ms": 9000, "mood": "chill", "source": "rule"},
    ]
    merged = merge_short_segments(segments, min_duration_ms=8000)
    assert len(merged) == 1
    assert merged[0]["end_ms"] == 9000
