from backend.detection.minor_cues import MinorCue
from backend.detection.minor_density import plan_minor_density


def test_plan_minor_density_caps_per_window():
    cues = [
        MinorCue(timestamp_ms=i * 500, score=0.1 * i)
        for i in range(1, 12)
    ]
    kept = plan_minor_density(cues, video_duration_sec=10.0, max_per_window=5)
    assert len(kept) == 5
    assert kept == sorted(kept, key=lambda c: c.timestamp_ms)
