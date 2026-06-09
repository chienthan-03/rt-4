def test_build_ffmpeg_filter_single_placement():
    from backend.render.renderer import build_ffmpeg_filter
    placements = [{
        "sound_file": "/sounds/vine_boom.mp3",
        "insert_ms": 3000,
        "volume": 0.85,
        "fade_out_ms": 50
    }]
    filter_str, inputs = build_ffmpeg_filter(placements, original_duration_s=10.0)
    assert "-i" in inputs
    assert "/sounds/vine_boom.mp3" in inputs
    assert "adelay=3000" in filter_str
    assert "amix" in filter_str
    assert "[aout]" in filter_str

def test_build_ffmpeg_filter_multiple_placements():
    from backend.render.renderer import build_ffmpeg_filter
    placements = [
        {"sound_file": "/a.mp3", "insert_ms": 1000, "volume": 0.8, "fade_out_ms": 0},
        {"sound_file": "/b.mp3", "insert_ms": 5000, "volume": 0.9, "fade_out_ms": 100},
    ]
    filter_str, inputs = build_ffmpeg_filter(placements, original_duration_s=15.0)
    assert inputs.count("-i") == 2
    assert "sfx0" in filter_str
    assert "sfx1" in filter_str
    assert "inputs=3" in filter_str  # [0:a] + sfx0 + sfx1

def test_build_ffmpeg_filter_empty_placements():
    from backend.render.renderer import build_ffmpeg_filter
    filter_str, inputs = build_ffmpeg_filter([], original_duration_s=10.0)
    assert inputs == []
    assert "amix=inputs=1" in filter_str  # just [0:a]
