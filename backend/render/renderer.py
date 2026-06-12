import subprocess


def build_background_filter_parts(
    bg_placements: list[dict],
    total_duration_s: float,
    start_input_idx: int,
    bg_volume: float = 0.15,
) -> tuple[list[str], list[str], str | None]:
    """Returns (stream_loop inputs, filter_parts, '[bgall]' label)."""
    if not bg_placements:
        return [], [], None

    inputs: list[str] = []
    filter_parts: list[str] = []
    bg_labels: list[str] = []

    # Make a copy of placements to avoid side effects
    placements = [p.copy() for p in bg_placements]

    # Pre-process placements for crossfades
    for i in range(len(placements)):
        p = placements[i]
        p_fade_in = p.get("fade_in_ms", 500)
        p_fade_out = p.get("fade_out_ms", 1000)
        p_crossfade = p.get("crossfade_ms", 0)

        if p_crossfade > 0 and i > 0:
            p["start_ms"] = max(0, p["start_ms"] - p_crossfade)
            p["fade_in_ms"] = p_crossfade
            placements[i - 1]["fade_out_ms"] = p_crossfade
        else:
            p["fade_in_ms"] = p_fade_in
            if "fade_out_ms" not in p:
                p["fade_out_ms"] = p_fade_out

    for i, p in enumerate(placements):
        idx = start_input_idx + i
        inputs.extend(["-stream_loop", "-1", "-i", p["sound_file"]])

        start_s = p["start_ms"] / 1000.0
        end_s = p["end_ms"] / 1000.0
        seg_dur = max(0.1, end_s - start_s)
        
        fade_in_s = p["fade_in_ms"] / 1000.0
        fade_out_s = p["fade_out_ms"] / 1000.0
        fade_out_offset = max(0.0, seg_dur - fade_out_s)

        filter_parts.append(
            f"[{idx}:a]atrim=start=0:end={seg_dur:.3f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:st=0:d={fade_in_s:.3f},"
            f"afade=t=out:st={fade_out_offset:.3f}:d={fade_out_s:.3f},"
            f"adelay={p['start_ms']}|{p['start_ms']},"
            f"apad=whole_dur={total_duration_s:.3f}[bg{i}]"
        )
        bg_labels.append(f"[bg{i}]")

    n = len(bg_labels)
    if n == 1:
        filter_parts.append(f"{bg_labels[0]}volume={bg_volume}[bgall]")
    else:
        filter_parts.append(
            f"{''.join(bg_labels)}amix=inputs={n}:normalize=0,volume={bg_volume}[bgall]"
        )
    return inputs, filter_parts, "[bgall]"



def _build_sfx_bus(sfx_placements: list[dict], original_duration_s: float) -> tuple[list[str], list[str], str | None]:
    if not sfx_placements:
        return [], [], None

    inputs: list[str] = []
    filter_parts: list[str] = []
    sfx_labels: list[str] = []

    for i, p in enumerate(sfx_placements):
        idx = i + 1
        volume = p["volume"]
        fade_out_s = p.get("fade_out_ms", 0) / 1000.0
        inputs.extend(["-i", p["sound_file"]])

        fade_part = (
            f",afade=t=out:st={max(0, original_duration_s - fade_out_s)}:d={fade_out_s}"
            if fade_out_s > 0
            else ""
        )
        filter_parts.append(
            f"[{idx}:a]volume={volume},adelay={p['insert_ms']}|{p['insert_ms']},"
            f"apad=whole_dur={original_duration_s}{fade_part}[sfx{i}]"
        )
        sfx_labels.append(f"[sfx{i}]")

    n = len(sfx_labels)
    if n == 1:
        filter_parts.append(f"{sfx_labels[0]}anull[sfxall]")
    else:
        filter_parts.append(
            f"{''.join(sfx_labels)}amix=inputs={n}:duration=longest:dropout_transition=0:"
            f"normalize=0,volume={n}[sfxall]"
        )
    return inputs, filter_parts, "[sfxall]"


BG_DUCK_THRESHOLD = 0.018
BG_DUCK_RATIO = 3
BG_DUCK_ATTACK = 50
BG_DUCK_RELEASE = 800


def build_ffmpeg_filter(
    sfx_placements: list[dict],
    original_duration_s: float,
    bg_placements: list[dict] | None = None,
    bg_volume: float = 0.15,
) -> tuple[str, list[str]]:
    """Build ffmpeg filter_complex string for mixing sound effects and background."""
    bg_placements = bg_placements or []

    if not sfx_placements and not bg_placements:
        return "[0:a]anull[aout]", []

    sfx_inputs, sfx_filters, sfx_label = _build_sfx_bus(sfx_placements, original_duration_s)
    bg_inputs, bg_filters, bg_label = build_background_filter_parts(
        bg_placements,
        original_duration_s,
        start_input_idx=len(sfx_placements) + 1,
        bg_volume=bg_volume,
    )

    all_filters = sfx_filters + bg_filters

    if not sfx_label and not bg_label:
        return "[0:a]anull[aout]", []

    filter_complex_parts = list(all_filters)

    if bg_label:
        # We have background. We always apply sidechain compression from original audio.
        filter_complex_parts.append("[0:a]asplit=2[aorig][asc]")
        filter_complex_parts.append(
            f"[{bg_label.strip('[]')}][asc]sidechaincompress=threshold={BG_DUCK_THRESHOLD}:"
            f"ratio={BG_DUCK_RATIO}:attack={BG_DUCK_ATTACK}:release={BG_DUCK_RELEASE}[bgducked]"
        )
        if sfx_label:
            filter_complex_parts.append(
                f"[aorig][{sfx_label.strip('[]')}][bgducked]amix=inputs=3:duration=first:"
                f"dropout_transition=0:normalize=0:weights=1 1 1,volume=3[aout]"
            )
        else:
            filter_complex_parts.append(
                f"[aorig][bgducked]amix=inputs=2:duration=first:dropout_transition=0:"
                f"normalize=0:weights=1 1,volume=2[aout]"
            )
    else:
        # We only have SFX.
        filter_complex_parts.append(
            f"[0:a][{sfx_label.strip('[]')}]amix=inputs=2:duration=first:dropout_transition=0:"
            f"normalize=0:weights=1 1,volume=2[aout]"
        )

    mix = ";".join(filter_complex_parts)
    return mix, sfx_inputs + bg_inputs


def render_video(
    input_video: str,
    placements: list[dict],
    output_path: str,
    bg_volume: float = 0.15,
) -> str:
    bg_placements = [p for p in placements if p.get("track") == "background"]
    sfx_placements = [p for p in placements if p.get("track") != "background"]

    if not sfx_placements and not bg_placements:
        subprocess.run(["ffmpeg", "-y", "-i", input_video, "-c", "copy", output_path],
                       check=True, capture_output=True)
        return output_path

    result = subprocess.run([
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", input_video
    ], capture_output=True, text=True, check=True)
    duration_s = float(result.stdout.strip())

    filter_complex, sound_inputs = build_ffmpeg_filter(
        sfx_placements,
        duration_s,
        bg_placements=bg_placements,
        bg_volume=bg_volume,
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", input_video,
        *sound_inputs,
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path
