import subprocess
from pathlib import Path


def build_ffmpeg_filter(placements: list[dict], original_duration_s: float) -> tuple[str, list[str]]:
    """Build ffmpeg filter_complex string for mixing sound effects."""
    inputs = []
    filter_parts = []
    amix_inputs = ["[0:a]"]

    for i, p in enumerate(placements):
        idx = i + 1
        offset_s = p["insert_ms"] / 1000.0
        volume = p["volume"]
        fade_out_s = p["fade_out_ms"] / 1000.0

        inputs.extend(["-i", p["sound_file"]])

        fade_part = f",afade=t=out:st={offset_s + original_duration_s - fade_out_s}:d={fade_out_s}" if fade_out_s > 0 else ""
        filter_parts.append(
            f"[{idx}:a]volume={volume},adelay={p['insert_ms']}|{p['insert_ms']},"
            f"apad=whole_dur={original_duration_s}{fade_part}[sfx{i}]"
        )
        amix_inputs.append(f"[sfx{i}]")

    mix = "".join(f"{part};" for part in filter_parts)
    mix += f"{''.join(amix_inputs)}amix=inputs={len(amix_inputs)}:duration=first:normalize=0[aout]"
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
