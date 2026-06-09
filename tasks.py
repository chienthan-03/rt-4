from celery import Celery
from backend.config import settings
import os, uuid, shutil
from pathlib import Path

app = Celery("meme_inserter", broker=settings.redis_url, backend=settings.redis_url)

@app.task(bind=True)
def process_video(self, video_path: str, job_id: str):
    work_dir = f"{settings.uploads_dir}/{job_id}"
    Path(work_dir).mkdir(parents=True, exist_ok=True)

    try:
        self.update_state(state="PROGRESS", meta={"step": "extracting"})
        from backend.ingestion.extractor import extract_audio, extract_frames
        wav_path = extract_audio(video_path, work_dir)
        frames_dir = f"{work_dir}/frames"
        extract_frames(video_path, frames_dir, fps=1)

        self.update_state(state="PROGRESS", meta={"step": "transcribing"})
        from backend.signals.transcript import transcribe, parse_whisper_segments, extract_transcript_events
        raw_transcript = transcribe(wav_path)
        segments = parse_whisper_segments(raw_transcript)
        transcript_events = extract_transcript_events(segments)
        transcript_skipped = raw_transcript.get("skipped", False)

        self.update_state(state="PROGRESS", meta={"step": "analyzing_signals"})
        from backend.signals.audio_signals import extract_audio_events
        from backend.signals.visual_signals import extract_scene_change_events
        from backend.signals.face_signals import extract_face_events
        audio_events = extract_audio_events(wav_path)
        visual_events = extract_scene_change_events(frames_dir)
        face_events = extract_face_events(frames_dir)

        all_events = transcript_events + audio_events + visual_events + face_events

        self.update_state(state="PROGRESS", meta={"step": "detecting_highlights"})
        from backend.detection.highlight_detector import detect_highlights
        from backend.detection.llm_validator import validate_highlights
        raw_highlights = detect_highlights(all_events)
        highlights = validate_highlights(raw_highlights)

        self.update_state(state="PROGRESS", meta={"step": "selecting_sounds"})
        from backend.sound.selector import select_sounds
        sound_selections = select_sounds(highlights)

        self.update_state(state="PROGRESS", meta={"step": "placing_sounds"})
        from backend.placement.placer import create_placements
        placements = create_placements(highlights, sound_selections)

        self.update_state(state="PROGRESS", meta={"step": "rendering"})
        from backend.render.renderer import render_video
        output_path = f"{settings.outputs_dir}/{job_id}.mp4"
        Path(settings.outputs_dir).mkdir(parents=True, exist_ok=True)
        render_video(video_path, placements, output_path)

        shutil.rmtree(work_dir, ignore_errors=True)
        unique_sounds = len({
            s["chosen_id"]
            for s in sound_selections
            if s and s.get("chosen_id")
        })
        result = {
            "status": "done",
            "output": output_path,
            "sounds_added": len(placements),
            "unique_sounds": unique_sounds,
            "highlights_detected": len(raw_highlights),
            "highlights_kept": len(highlights),
        }
        if transcript_skipped:
            result["transcript_skipped"] = True
            result["transcript_note"] = (
                "Bỏ qua nhận dạng giọng nói (OpenRouter audio cần >= $0.50 credit). "
                "Vẫn dùng tín hiệu âm thanh/hình ảnh để chèn sound."
            )
        return result

    except Exception as e:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise
