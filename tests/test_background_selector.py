# tests/test_background_selector.py
from unittest.mock import patch

import pytest

from backend.sound.background_selector import select_background_for_segments


MOCK_SOUNDS = [
    {"id": "a1", "tier": "background", "mood": "chill", "file_path": "/bg/chill1.mp3", "name": "chill1"},
    {"id": "a2", "tier": "background", "mood": "chill", "file_path": "/bg/chill2.mp3", "name": "chill2"},
    {"id": "b1", "tier": "background", "mood": "dramatic", "file_path": "/bg/dram1.mp3", "name": "dram1"},
]


@patch("backend.sound.background_selector._background_pool", return_value=MOCK_SOUNDS)
@patch("backend.sound.background_selector.Path")
def test_selects_matching_mood(mock_path, mock_pool):
    mock_path.return_value.is_file.return_value = True
    segments = [
        {"start_ms": 0, "end_ms": 10000, "mood": "chill", "source": "rule"},
        {"start_ms": 10000, "end_ms": 20000, "mood": "dramatic", "source": "rule"},
    ]
    result = select_background_for_segments(segments)
    assert len(result) == 2
    assert result[0]["mood"] == "chill"
    assert result[1]["mood"] == "dramatic"
    assert result[0]["sound_id"] != result[1]["sound_id"] or result[0]["mood"] != result[1]["mood"]


@patch("backend.sound.background_selector._background_pool", return_value=[])
def test_empty_pool_returns_empty(mock_pool):
    segments = [{"start_ms": 0, "end_ms": 10000, "mood": "chill", "source": "rule"}]
    assert select_background_for_segments(segments) == []
