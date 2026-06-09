import subprocess
from pathlib import Path

def extract_audio(video_path: str, output_dir: str) -> str:
    """Extract mono 16kHz WAV from video."""
    out = str(Path(output_dir) / (Path(video_path).stem + ".wav"))
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path,
        "-ar", "16000", "-ac", "1", "-vn", out
    ], check=True, capture_output=True)
    return out

def extract_frames(video_path: str, output_dir: str, fps: float = 1.0) -> list[str]:
    """Extract frames at given fps. Returns list of jpg paths."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    pattern = str(Path(output_dir) / "frame_%04d.jpg")
    subprocess.run([
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"fps={fps}", pattern
    ], check=True, capture_output=True)
    return sorted(str(p) for p in Path(output_dir).glob("frame_*.jpg"))

def get_video_duration_s(video_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    result = subprocess.run([
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", video_path
    ], capture_output=True, text=True, check=True)
    import json
    data = json.loads(result.stdout)
    for s in data["streams"]:
        if s.get("codec_type") == "video":
            # Some formats/codecs write duration as string, check type
            dur = s.get("duration")
            if dur is not None:
                return float(dur)
    return 0.0
