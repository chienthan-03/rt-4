from unittest.mock import MagicMock, patch

import httpx
import pytest

from backend.main import app


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client


@pytest.mark.anyio
@patch("backend.main.process_video")
async def test_upload_passes_major_volume(mock_process_video, client, sample_video_path):
    mock_task = MagicMock()
    mock_task.id = "task-abc"
    mock_process_video.delay.return_value = mock_task

    with open(sample_video_path, "rb") as video_file:
        response = await client.post(
            "/upload",
            files={"file": ("test.mp4", video_file, "video/mp4")},
            data={"major_volume": "0.45", "minor_volume": "0.35", "bg_volume": "0.15"},
        )

    assert response.status_code == 200
    assert response.json()["task_id"] == "task-abc"
    mock_process_video.delay.assert_called_once()
    args = mock_process_video.delay.call_args[0]
    assert args[2] == 0.45
    assert args[4] == 0.35
    assert args[5] == 0.15


@pytest.mark.anyio
@patch("backend.main.process_video")
async def test_upload_passes_meme_volume_legacy(mock_process_video, client, sample_video_path):
    mock_task = MagicMock()
    mock_task.id = "task-legacy"
    mock_process_video.delay.return_value = mock_task

    with open(sample_video_path, "rb") as video_file:
        response = await client.post(
            "/upload",
            files={"file": ("test.mp4", video_file, "video/mp4")},
            data={"meme_volume": "0.45"},
        )

    assert response.status_code == 200
    assert mock_process_video.delay.call_args[0][2] == 0.45


@pytest.mark.anyio
@patch("backend.main.process_video")
async def test_upload_defaults_volumes(mock_process_video, client, sample_video_path):
    mock_task = MagicMock()
    mock_task.id = "task-default"
    mock_process_video.delay.return_value = mock_task

    with open(sample_video_path, "rb") as video_file:
        response = await client.post(
            "/upload",
            files={"file": ("test.mp4", video_file, "video/mp4")},
        )

    assert response.status_code == 200
    args = mock_process_video.delay.call_args[0]
    assert args[2] == 0.5
    assert args[4] == 0.35
    assert args[5] == 0.15


@pytest.mark.anyio
@patch("backend.main.process_video")
async def test_upload_passes_niche(mock_process_video, client, sample_video_path):
    mock_task = MagicMock()
    mock_task.id = "task-niche"
    mock_process_video.delay.return_value = mock_task

    with open(sample_video_path, "rb") as video_file:
        response = await client.post(
            "/upload",
            files={"file": ("test.mp4", video_file, "video/mp4")},
            data={"niche": "edu"},
        )

    assert response.status_code == 200
    assert response.json()["niche"] == "edu"
    assert mock_process_video.delay.call_args[0][3] == "edu"


@pytest.mark.anyio
async def test_upload_rejects_invalid_niche(client, sample_video_path):
    with open(sample_video_path, "rb") as video_file:
        response = await client.post(
            "/upload",
            files={"file": ("test.mp4", video_file, "video/mp4")},
            data={"niche": "gaming"},
        )

    assert response.status_code == 400
    assert "niche" in response.json()["detail"].lower()


@pytest.mark.anyio
async def test_upload_rejects_invalid_major_volume(client, sample_video_path):
    with open(sample_video_path, "rb") as video_file:
        response = await client.post(
            "/upload",
            files={"file": ("test.mp4", video_file, "video/mp4")},
            data={"major_volume": "2.5"},
        )

    assert response.status_code == 400
    assert "major volume" in response.json()["detail"].lower()


@pytest.mark.anyio
@patch("backend.main.process_video")
async def test_upload_accepts_zero_volume(mock_process_video, client, sample_video_path):
    mock_task = MagicMock()
    mock_task.id = "task-mute"
    mock_process_video.delay.return_value = mock_task

    with open(sample_video_path, "rb") as video_file:
        response = await client.post(
            "/upload",
            files={"file": ("test.mp4", video_file, "video/mp4")},
            data={"major_volume": "0"},
        )

    assert response.status_code == 200
    assert mock_process_video.delay.call_args[0][2] == 0.0
