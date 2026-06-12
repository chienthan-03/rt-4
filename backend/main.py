from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uuid, shutil
from backend.config import settings
from backend.detection.niche import DEFAULT_NICHE, normalize_niche
from tasks import process_video

app = FastAPI(title="Meme Sound Inserter")
app.mount("/static", StaticFiles(directory="frontend"), name="static")

Path(settings.uploads_dir).mkdir(parents=True, exist_ok=True)
Path(settings.outputs_dir).mkdir(parents=True, exist_ok=True)

@app.get("/")
def index():
    return FileResponse("frontend/index.html")

@app.post("/upload")
async def upload_video(
    file: UploadFile = File(...),
    major_volume: float | None = Form(None),
    minor_volume: float = Form(0.35),
    bg_volume: float = Form(0.15),
    meme_volume: float | None = Form(None),
    niche: str = Form(DEFAULT_NICHE),
    enable_background: bool = Form(True),
):
    resolved_major = major_volume if major_volume is not None else (meme_volume if meme_volume is not None else 0.5)

    for label, value in (
        ("Major volume", resolved_major),
        ("Minor volume", minor_volume),
        ("Background volume", bg_volume),
    ):
        if value < 0.0 or value > 2.0:
            raise HTTPException(400, f"{label} must be between 0.0 and 2.0")

    try:
        niche = normalize_niche(niche)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    is_video_type = file.content_type and file.content_type.startswith("video/")
    is_video_name = file.filename and Path(file.filename).suffix.lower() in {
        ".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"
    }
    if not is_video_type and not is_video_name:
        raise HTTPException(400, "File must be a video")

    job_id = str(uuid.uuid4())
    video_path = f"{settings.uploads_dir}/{job_id}_{file.filename}"

    with open(video_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    task = process_video.delay(
        video_path,
        job_id,
        resolved_major,
        niche,
        minor_volume,
        bg_volume,
        enable_background,
    )
    return {"job_id": job_id, "task_id": task.id, "niche": niche}

@app.get("/status/{task_id}")
def get_status(task_id: str):
    from celery.result import AsyncResult
    from tasks import app as celery_app
    result = AsyncResult(task_id, app=celery_app)
    response = {"status": result.status}
    if result.status == "PROGRESS":
        response["step"] = result.info.get("step", "")
    elif result.status == "SUCCESS":
        response["result"] = result.result
    elif result.status == "FAILURE":
        response["error"] = str(result.result)
    return JSONResponse(response)

@app.get("/download/{job_id}")
def download_video(job_id: str):
    path = f"{settings.outputs_dir}/{job_id}.mp4"
    if not Path(path).exists():
        raise HTTPException(404, "Video not found or not ready")
    return FileResponse(path, media_type="video/mp4", filename=f"meme_{job_id[:8]}.mp4")
