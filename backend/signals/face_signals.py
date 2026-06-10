import urllib.request
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_detector/blaze_face_short_range/float16/1/"
    "blaze_face_short_range.tflite"
)
MODEL_PATH = Path(__file__).resolve().parent.parent / "models" / "blaze_face_short_range.tflite"


def _ensure_model() -> Path:
    if MODEL_PATH.exists():
        return MODEL_PATH

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
    return MODEL_PATH


def extract_face_events(frames_dir: str) -> list[dict]:
    frame_paths = sorted(Path(frames_dir).glob("frame_*.jpg"))
    events = []

    options = vision.FaceDetectorOptions(
        base_options=python.BaseOptions(model_asset_path=str(_ensure_model())),
        min_detection_confidence=0.5,
    )
    detector = vision.FaceDetector.create_from_options(options)
    try:
        for i, fp in enumerate(frame_paths):
            frame = cv2.imread(str(fp))
            if frame is None:
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            results = detector.detect(mp_image)
            if results.detections:
                events.append({
                    "timestamp_ms": i * 1000,
                    "score": 0.2,
                    "type": "face_detected",
                    "context_text": "",
                })
    finally:
        detector.close()

    return events
