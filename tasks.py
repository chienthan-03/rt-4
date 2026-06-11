from celery import Celery
from backend.config import settings
import shutil
from pathlib import Path

app = Celery("meme_inserter", broker=settings.redis_url, backend=settings.redis_url)

@app.task(bind=True)
def process_video(
    self,
    video_path: str,
    job_id: str,
    major_volume: float = 0.5,
    niche: str = "entertainment",
    minor_volume: float = 0.35,
    bg_volume: float = 0.15,
    meme_volume: float | None = None,
):
    if meme_volume is not None:
        major_volume = meme_volume

    work_dir = f"{settings.uploads_dir}/{job_id}"
    Path(work_dir).mkdir(parents=True, exist_ok=True)

    try:
        self.update_state(state="PROGRESS", meta={"step": "extracting"})
        from backend.ingestion.extractor import extract_audio, extract_frames, get_video_duration_s
        duration_sec = get_video_duration_s(video_path)
        duration_ms = int(duration_sec * 1000)
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
        from backend.signals.audio_signals import extract_audio_events, extract_rms_segments
        from backend.signals.visual_signals import extract_scene_change_events
        from backend.signals.face_signals import extract_face_events
        audio_events = extract_audio_events(wav_path)
        rms_segments = extract_rms_segments(wav_path)
        visual_events = extract_scene_change_events(frames_dir)
        face_events = extract_face_events(frames_dir)

        all_events = transcript_events + audio_events + visual_events + face_events

        self.update_state(state="PROGRESS", meta={"step": "detecting_highlights"})
        from backend.detection.highlight_detector import detect_highlights
        from backend.detection.llm_validator import validate_highlights
        raw_highlights = detect_highlights(all_events)
        highlights = validate_highlights(raw_highlights)
        from backend.detection.density import apply_density_cap
        highlights = apply_density_cap(highlights, duration_sec, niche=niche)

        self.update_state(state="PROGRESS", meta={"step": "selecting_sounds"})
        from backend.sound.selector import select_sounds
        sound_selections = select_sounds(highlights)

        from backend.detection.minor_cues import (
            extract_energy_dip_cues,
            extract_minor_cues,
            extract_speech_pause_cues,
        )
        from backend.detection.minor_density import max_minor_per_window, plan_minor_density
        from backend.sound.minor_selector import select_fill_sounds, select_minor_sounds
        minor_cues: list = []
        minor_selections: list = []
        if max_minor_per_window(niche) > 0:
            all_minor_cues = (
                extract_minor_cues(visual_events, major_highlights=highlights)
                + extract_speech_pause_cues(segments, major_highlights=highlights)
                + extract_energy_dip_cues(rms_segments, major_highlights=highlights)
            )
            all_minor_cues.sort(key=lambda c: c.timestamp_ms)
            minor_cues = plan_minor_density(all_minor_cues, duration_sec, niche=niche)
            minor_selections = select_minor_sounds(minor_cues)

        self.update_state(state="PROGRESS", meta={"step": "placing_sounds"})
        from backend.detection.background_detector import (
            get_background_segments,
            select_background_mood,
            should_use_background,
        )
        from backend.placement.placer import (
            create_background_placements,
            create_minor_placements,
            create_placements,
            gap_fill_pass,
            merge_placements,
        )
        from backend.sound.background_selector import select_background_sound

        major_placements = create_placements(
            highlights, sound_selections, major_volume=major_volume
        )
        minor_placements = create_minor_placements(
            minor_cues, minor_selections, minor_volume=minor_volume
        )
        placements = merge_placements(major_placements, minor_placements)

        fill_selections = select_fill_sounds(max(1, duration_ms // 8000))
        placements = gap_fill_pass(
            placements,
            fill_selections,
            total_duration_ms=duration_ms,
            filler_volume=minor_volume,
        )

        bg_placements: list[dict] = []
        if should_use_background(rms_segments):
            mood = select_background_mood(highlights)
            bg_sound = select_background_sound(mood)
            bg_segments = get_background_segments(rms_segments)
            bg_placements = create_background_placements(
                bg_sound,
                bg_segments,
                major_placements,
                bg_volume=bg_volume,
            )

        all_placements = sorted(
            placements + bg_placements,
            key=lambda p: p["insert_ms"],
        )

        self.update_state(state="PROGRESS", meta={"step": "rendering"})
        from backend.render.renderer import render_video
        output_path = f"{settings.outputs_dir}/{job_id}.mp4"
        Path(settings.outputs_dir).mkdir(parents=True, exist_ok=True)
        render_video(video_path, all_placements, output_path, bg_volume=bg_volume)

        shutil.rmtree(work_dir, ignore_errors=True)
        unique_sounds = len({
            s["chosen_id"]
            for s in sound_selections
            if s and s.get("chosen_id")
        })
        minor_count = sum(
            1 for p in placements if p.get("track") in ("minor", "filler")
        )
        result = {
            "status": "done",
            "output": output_path,
            "sounds_added": len(all_placements),
            "major_sounds": len(major_placements),
            "minor_sounds": minor_count,
            "background_segments": len(bg_placements),
            "unique_sounds": unique_sounds,
            "highlights_detected": len(raw_highlights),
            "highlights_kept": len(highlights),
            "minor_cues": len(minor_cues),
            "niche": niche,
        }
        if transcript_skipped:
            result["transcript_skipped"] = True
            result["transcript_note"] = (
                "Bỏ qua nhận dạng giọng nói (OpenRouter audio cần >= $0.50 credit). "
                "Vẫn dùng tín hiệu âm thanh/hình ảnh để chèn sound."
            )
        return result

    except Exception:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise
