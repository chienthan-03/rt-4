import cv2
import numpy as np
from pathlib import Path

def extract_scene_change_events(frames_dir: str, threshold: float = 38.0) -> list[dict]:
    frame_paths = sorted(Path(frames_dir).glob("frame_*.jpg"))
    events = []
    prev_gray = None

    for i, fp in enumerate(frame_paths):
        frame = cv2.imread(str(fp), cv2.IMREAD_GRAYSCALE)
        if frame is None:
            continue
        if prev_gray is not None:
            diff = np.mean(np.abs(frame.astype(float) - prev_gray.astype(float)))
            if diff > threshold:
                # frame index → approximate ms (assuming 1fps extraction)
                events.append({
                    "timestamp_ms": i * 1000,
                    "score": min(diff / 100.0, 0.6),
                    "type": "scene_change",
                    "context_text": ""
                })
        prev_gray = frame

    return events
