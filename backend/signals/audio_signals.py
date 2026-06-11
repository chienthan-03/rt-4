import librosa
import numpy as np

def extract_audio_events(wav_path: str) -> list[dict]:
    y, sr = librosa.load(wav_path, sr=16000, mono=True)
    events = []

    if len(y) == 0:
        return []

    # RMS energy per frame
    hop_length = 512
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    times_ms = (librosa.frames_to_time(
        np.arange(len(rms)), sr=sr, hop_length=hop_length
    ) * 1000).astype(int)

    # Detect spikes using RMS deltas (changes)
    deltas = np.diff(rms)
    mean_delta = np.mean(deltas)
    std_delta = np.std(deltas)
    threshold = mean_delta + 2 * std_delta

    for i in range(len(deltas)):
        if deltas[i] > threshold and deltas[i] > 0.02:
            denom = std_delta if std_delta > 1e-6 else 1e-6
            score = min((deltas[i] - threshold) / denom * 0.3 + 0.5, 1.0)
            score = max(0.1, score)
            events.append({
                "timestamp_ms": int(times_ms[i+1]),
                "score": float(score),
                "type": "audio_spike",
                "context_text": ""
            })

    # Detect silence breaks (> 1000ms silence → sound)
    # Use split only if there is non-silent audio, wrap in try/except
    try:
        intervals = librosa.effects.split(y, top_db=30)
        for start, end in intervals:
            start_ms = int(start / sr * 1000)
            # silence before this interval
            if start_ms > 1000:
                events.append({
                    "timestamp_ms": start_ms,
                    "score": 0.5,
                    "type": "silence_break",
                    "context_text": ""
                })
    except Exception:
        pass

    return events

def extract_rms_segments(wav_path: str, segment_duration_s: float = 10.0) -> list[dict]:
    y, sr = librosa.load(wav_path, sr=16000, mono=True)
    if len(y) == 0:
        return []
    
    hop_length = 512
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    
    segment_duration_ms = int(segment_duration_s * 1000)
    samples_per_segment = int(segment_duration_s * sr)
    frames_per_segment = librosa.samples_to_frames(samples_per_segment, hop_length=hop_length)
    
    segments = []
    num_frames = len(rms)
    for i in range(0, num_frames, frames_per_segment):
        segment_rms = rms[i:i+frames_per_segment]
        start_ms = int(librosa.frames_to_time(i, sr=sr, hop_length=hop_length) * 1000)
        end_ms = min(start_ms + segment_duration_ms, int(len(y) / sr * 1000))
        
        segments.append({
            "start_ms": start_ms,
            "end_ms": end_ms,
            "rms_mean": float(np.mean(segment_rms))
        })
    
    return segments
