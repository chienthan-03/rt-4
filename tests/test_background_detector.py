def test_should_use_background():
    from backend.detection.background_detector import should_use_background
    segments = [
        {"start_ms": 0, "end_ms": 10000, "rms_mean": 0.01}, # silent
        {"start_ms": 10000, "end_ms": 20000, "rms_mean": 0.05}, # loud
        {"start_ms": 20000, "end_ms": 30000, "rms_mean": 0.01}, # silent
    ]
    assert should_use_background(segments) == True

    segments2 = [
        {"start_ms": 0, "end_ms": 10000, "rms_mean": 0.05}, # loud
        {"start_ms": 10000, "end_ms": 20000, "rms_mean": 0.05}, # loud
        {"start_ms": 20000, "end_ms": 30000, "rms_mean": 0.05}, # loud
    ]
    assert should_use_background(segments2) == False
