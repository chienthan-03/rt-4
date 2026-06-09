import numpy as np
import soundfile as sf
from pathlib import Path

def test_extract_audio_events_returns_list(tmp_path):
    """Silent WAV should return empty list (no spikes)."""
    from backend.signals.audio_signals import extract_audio_events
    wav_path = str(tmp_path / "silent.wav")
    silent = np.zeros(16000 * 3, dtype=np.float32)  # 3s silence
    sf.write(wav_path, silent, 16000)
    events = extract_audio_events(wav_path)
    assert isinstance(events, list)
    # All events must have required keys
    for e in events:
        assert "timestamp_ms" in e
        assert "score" in e
        assert "type" in e

def test_extract_audio_events_detects_spike(tmp_path):
    """A sudden loud segment after silence should produce an audio_spike event."""
    from backend.signals.audio_signals import extract_audio_events
    wav_path = str(tmp_path / "spike.wav")
    sr = 16000
    silence = np.zeros(sr, dtype=np.float32)           # 1s silence
    spike = np.sin(2 * np.pi * 440 * np.linspace(0, 0.5, sr // 2)).astype(np.float32)  # 0.5s tone
    audio = np.concatenate([silence, spike])
    sf.write(wav_path, audio, sr)
    events = extract_audio_events(wav_path)
    spike_events = [e for e in events if e["type"] == "audio_spike"]
    assert len(spike_events) > 0
