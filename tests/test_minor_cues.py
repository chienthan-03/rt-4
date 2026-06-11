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


def test_extract_speech_pause_cues():
    from backend.detection.minor_cues import extract_speech_pause_cues

    segments = [
        {"start_ms": 0, "end_ms": 1000, "text": "hello"},
        {"start_ms": 4000, "end_ms": 6000, "text": "world"},
    ]
    major = [Highlight(start_ms=400, end_ms=600, peak_ms=500, score=0.9, impact_score=60)]
    cues = extract_speech_pause_cues(segments, major_highlights=major)
    assert len(cues) == 1
    assert cues[0].cue_type == "speech_pause"
    assert cues[0].timestamp_ms == 2500


def test_extract_speech_pause_ignores_short_gap():
    from backend.detection.minor_cues import extract_speech_pause_cues

    segments = [
        {"start_ms": 0, "end_ms": 1000, "text": "a"},
        {"start_ms": 2000, "end_ms": 3000, "text": "b"},
    ]
    cues = extract_speech_pause_cues(segments)
    assert cues == []


def test_extract_energy_dip_cues():
    from backend.detection.minor_cues import extract_energy_dip_cues

    rms_segments = [
        {"start_ms": 0, "end_ms": 10000, "rms_mean": 0.5},
        {"start_ms": 10000, "end_ms": 20000, "rms_mean": 0.01},
        {"start_ms": 20000, "end_ms": 30000, "rms_mean": 0.5},
    ]
    major = [Highlight(start_ms=900, end_ms=1100, peak_ms=1000, score=0.9, impact_score=60)]
    cues = extract_energy_dip_cues(rms_segments, major_highlights=major)
    assert len(cues) == 1
    assert cues[0].cue_type == "energy_dip"
    assert cues[0].timestamp_ms == 15000
