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
    assert "amix=inputs=2:duration=longest" in filter_str
    assert "volume=2[sfxall]" in filter_str
    assert "[0:a][sfxall]amix=inputs=2" in filter_str

def test_build_ffmpeg_filter_empty_placements():
    from backend.render.renderer import build_ffmpeg_filter
    filter_str, inputs = build_ffmpeg_filter([], original_duration_s=10.0)
    assert inputs == []
    assert "[0:a]anull[aout]" in filter_str


def test_build_background_filter_parts():
    from backend.render.renderer import build_background_filter_parts

    bg_placements = [
        {
            "sound_file": "/sounds/ambient.mp3",
            "start_ms": 0,
            "end_ms": 15000,
            "volume": 0.15,
        },
        {
            "sound_file": "/sounds/ambient.mp3",
            "start_ms": 20000,
            "end_ms": 30000,
            "volume": 0.15,
        },
    ]
    inputs, filters, label = build_background_filter_parts(
        bg_placements, total_duration_s=30.0, start_input_idx=3, bg_volume=0.15
    )
    joined = ";".join(filters)
    assert "-stream_loop" in inputs
    assert "atrim" in joined
    assert "asetpts" in joined
    assert "bgall" in joined
    assert label == "[bgall]"


def test_build_background_filter_parts_uses_dynamic_fade():
    from backend.render.renderer import build_background_filter_parts

    bg_placements = [{
        "sound_file": "/bg/chill.mp3",
        "start_ms": 0,
        "end_ms": 20000,
        "fade_in_ms": 500,
        "fade_out_ms": 1000,
        "crossfade_ms": 0,
    }]
    _, filters, _ = build_background_filter_parts(
        bg_placements, total_duration_s=20.0, start_input_idx=1, bg_volume=0.15
    )
    joined = ";".join(filters)
    assert "afade=t=in:st=0:d=0.5" in joined
    assert "afade=t=out" in joined


def test_build_ffmpeg_filter_includes_sidechain_when_background():
    from backend.render.renderer import build_ffmpeg_filter

    sfx = [{"sound_file": "/a.mp3", "insert_ms": 1000, "volume": 0.5, "fade_out_ms": 0}]
    bg = [{
        "sound_file": "/bg/chill.mp3",
        "start_ms": 0,
        "end_ms": 10000,
        "fade_in_ms": 500,
        "fade_out_ms": 0,
        "crossfade_ms": 0,
        "track": "background",
    }]
    filter_str, _ = build_ffmpeg_filter(sfx, 10.0, bg_placements=bg, bg_volume=0.15)
    assert "sidechaincompress" in filter_str
    assert "[bgducked]" in filter_str
    assert "inputs=3" in filter_str
