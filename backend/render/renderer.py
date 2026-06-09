import subprocess
from pathlib import Path


def build_ffmpeg_filter(placements: list[dict], original_duration_s: float) -> tuple[str, list[str]]:
    """Build ffmpeg filter_complex string for mixing sound effects."""
    if not placements:
        return "[0:a]anull[aout]", []

    inputs = []
    filter_parts = []
    sfx_labels = []

    for i, p in enumerate(placements):
        idx = i + 1
        volume = p["volume"]
        fade_out_s = p["fade_out_ms"] / 1000.0

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

    n = len(placements)
    sfx_chain = ";".join(filter_parts)

    if n == 1:
        mix = (
            f"{sfx_chain};"
            f"[0:a][sfx0]amix=inputs=2:duration=first:dropout_transition=0:"
            f"normalize=0:weights=1 1,volume=2[aout]"
        )
        return mix, inputs

    # Mix SFX on a separate bus (amix divides by N — compensate with volume=N),
    # then overlay on the original track without ducking the main audio.
    sfx_bus = (
        f"{''.join(sfx_labels)}amix=inputs={n}:duration=longest:dropout_transition=0:"
        f"normalize=0,volume={n}[sfxall]"
    )
    mix = (
        f"{sfx_chain};{sfx_bus};"
        f"[0:a][sfxall]amix=inputs=2:duration=first:dropout_transition=0:"
        f"normalize=0:weights=1 1,volume=2[aout]"
    )
    return mix, inputs


def render_video(
    input_video: str,
    placements: list[dict],
    output_path: str
) -> str:
    if not placements:
        # No sounds — just copy
        subprocess.run(["ffmpeg", "-y", "-i", input_video, "-c", "copy", output_path],
                       check=True, capture_output=True)
        return output_path

    # Get video duration
    result = subprocess.run([
        "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", input_video
    ], capture_output=True, text=True, check=True)
    duration_s = float(result.stdout.strip())

    filter_complex, sound_inputs = build_ffmpeg_filter(placements, duration_s)

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
