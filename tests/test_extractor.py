import pytest
from pathlib import Path

def test_extract_audio_creates_wav(tmp_path, sample_video_path):
    from backend.ingestion.extractor import extract_audio
    wav_path = extract_audio(sample_video_path, str(tmp_path))
    assert Path(wav_path).exists()
    assert wav_path.endswith(".wav")

def test_extract_frames_returns_list(tmp_path, sample_video_path):
    from backend.ingestion.extractor import extract_frames
    frames = extract_frames(sample_video_path, str(tmp_path), fps=1)
    assert len(frames) > 0
    assert all(Path(f).exists() for f in frames)
