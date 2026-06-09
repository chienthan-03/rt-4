import cv2
import mediapipe as mp
from pathlib import Path

# MediaPipe face detection initializer
mp_face = mp.solutions.face_detection

def extract_face_events(frames_dir: str) -> list[dict]:
    frame_paths = sorted(Path(frames_dir).glob("frame_*.jpg"))
    events = []

    with mp_face.FaceDetection(min_detection_confidence=0.5) as detector:
        for i, fp in enumerate(frame_paths):
            frame = cv2.imread(str(fp))
            if frame is None:
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = detector.process(rgb)
            if results.detections:
                # Face detected — low baseline score, enriched by other signals
                events.append({
                    "timestamp_ms": i * 1000,
                    "score": 0.2,
                    "type": "face_detected",
                    "context_text": ""
                })

    return events
