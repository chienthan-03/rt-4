# Meme Volume Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a volume slider to the frontend and pass the `meme_volume` parameter down through the API to the Celery task and FFmpeg renderer, allowing users to control meme sound effect volume.

**Architecture:** We will modify the `/upload` API endpoint to accept `meme_volume: float = 0.5` via Form data. We'll update the `process_video` task signature and `create_placements` to use this dynamic value instead of the hardcoded `0.85`. The frontend will convert the 0-100 UI slider value to a 0.0-2.0 float range before submitting.

**Tech Stack:** FastAPI, Celery, Python, Vanilla JS (Frontend)

---

### Task 1: Backend Placement Logic (`placer.py`)

**Files:**
- Modify: `c:/Publish/rt-4/backend/placement/placer.py`

- [ ] **Step 1: Write minimal implementation**
Modify `create_placements` signature to accept `meme_volume: float = 0.85` and use it instead of the hardcoded 0.85.
```python
def create_placements(
    highlights: list[Highlight],
    sound_selections: list[dict],
    meme_volume: float = 0.85
) -> list[dict]:
    # ...
            "end_ms": insert_ms + duration_ms,
            "volume": meme_volume,
            "fade_in_ms": 0,
    # ...
```

- [ ] **Step 2: Commit**
```bash
git add backend/placement/placer.py
git commit -m "feat: use dynamic meme_volume in placer"
```

### Task 2: Backend Celery Task (`tasks.py`)

**Files:**
- Modify: `c:/Publish/rt-4/tasks.py`

- [ ] **Step 1: Write minimal implementation**
Update `process_video` signature to accept `meme_volume: float = 0.85` and pass it to `create_placements`.
```python
@app.task(bind=True)
def process_video(self, video_path: str, job_id: str, meme_volume: float = 0.85):
    # ...
        from backend.placement.placer import create_placements
        placements = create_placements(highlights, sound_selections, meme_volume=meme_volume)
    # ...
```

- [ ] **Step 2: Commit**
```bash
git add tasks.py
git commit -m "feat: pass meme_volume through celery task"
```

### Task 3: Backend API Endpoint (`main.py`)

**Files:**
- Modify: `c:/Publish/rt-4/backend/main.py`

- [ ] **Step 1: Write minimal implementation**
Update `/upload` endpoint to accept `meme_volume`.
```python
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
# ...
@app.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    meme_volume: float = Form(0.5)
):
    # validate meme_volume between 0.0 and 2.0
    if meme_volume < 0.0 or meme_volume > 2.0:
        raise HTTPException(400, "meme_volume must be between 0.0 and 2.0")
    # ...
    task = process_video.delay(video_path, job_id, meme_volume)
    return {"job_id": job_id, "task_id": task.id}
```

- [ ] **Step 2: Commit**
```bash
git add backend/main.py
git commit -m "feat: accept meme_volume in upload api"
```

### Task 4: Frontend UI (`frontend/index.html` and JS)

**Files:**
- Modify: `c:/Publish/rt-4/frontend/index.html` (or corresponding JS file)

- [ ] **Step 1: Write minimal implementation**
Add a volume slider to the frontend HTML.
```html
<label for="meme-volume-slider">Meme Volume: <span id="meme-volume-label">50%</span></label>
<input type="range" id="meme-volume-slider" min="0" max="100" value="50">
```
In the Javascript that handles the upload:
```javascript
// Example JS logic
const volumeSlider = document.getElementById('meme-volume-slider');
const volumeLabel = document.getElementById('meme-volume-label');

volumeSlider.addEventListener('input', (e) => {
    volumeLabel.innerText = `${e.target.value}%`;
});

// Inside upload function:
const formData = new FormData();
formData.append('file', fileInput.files[0]);
// Convert 0-100 to 0.0 - 2.0 range (e.g. 50% = 1.0, wait... 50% usually means 0.5, let's keep 50% = 0.5 so 100% = 1.0. The user agreed default 50% is half max volume).
const volumeFloat = parseFloat(volumeSlider.value) / 100.0;
formData.append('meme_volume', volumeFloat);
```

- [ ] **Step 2: Commit**
```bash
git add frontend/
git commit -m "feat: add meme volume slider to frontend"
```
