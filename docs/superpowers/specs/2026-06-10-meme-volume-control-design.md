# Meme Volume Control Design

## 1. Overview
The current system hardcodes the volume of inserted meme sound effects to `0.85` (85%), which can often overpower the original audio of the uploaded video. This project introduces a manual volume control feature, allowing users to adjust the meme sound effect volume via a slider on the frontend before processing the video.

## 2. Architecture & Components

### 2.1 Frontend
- Add a volume slider input to `index.html` (or the main upload form component).
- Range: 0 to 100 (percentage).
- Default value: 50.
- The selected value will be sent to the backend as a new form data parameter `meme_volume` (converted to a 0.0 - 1.0 float or sent as integer and converted in backend) during the `/upload` API request.

### 2.2 Backend API (`main.py`)
- Update the `/upload` endpoint to accept a new `Form(...)` parameter: `meme_volume: float = 0.5`.
- Validate that `meme_volume` is within a reasonable range (0.0 to 2.0).
- Pass `meme_volume` to the Celery task: `process_video.delay(video_path, job_id, meme_volume)`.

### 2.3 Task Processing (`tasks.py`)
- Update the `process_video` task signature to accept `meme_volume: float = 0.85` (defaulting to old behavior if not provided).
- Pass the `meme_volume` parameter down the pipeline, specifically to `create_placements`.

### 2.4 Placement Logic (`placer.py`)
- Update `create_placements` signature: `def create_placements(highlights, sound_selections, meme_volume=0.85)`.
- Replace the hardcoded `"volume": 0.85` with `"volume": meme_volume` when generating placement dicts.

### 2.5 Rendering (`renderer.py`)
- No changes required. The renderer already reads `p["volume"]` from the placement dict and applies it via FFmpeg's `volume` filter.

## 3. Data Flow
1. User adjusts slider on UI -> selects `0.5` (50%).
2. Frontend sends `POST /upload` with `file=video.mp4` and `meme_volume=0.5`.
3. FastAPI endpoint receives `meme_volume` and calls `process_video.delay(..., meme_volume=0.5)`.
4. Celery task `process_video` calls `create_placements(..., meme_volume=0.5)`.
5. `placer.py` creates placements with `"volume": 0.5`.
6. `renderer.py` applies `volume=0.5` via FFmpeg.

## 4. Error Handling
- Invalid `meme_volume` values from the frontend (e.g. text or out of bounds) will be caught by FastAPI's validation.
- Missing `meme_volume` defaults gracefully to 0.5 (or 0.85 for backward compatibility).

## 5. Testing
- Test the upload endpoint with and without the `meme_volume` parameter.
- Test edge cases for volume (0.0 for mute, >1.0 for boosting).
- Verify the generated FFmpeg command includes the correct volume filter parameter.
