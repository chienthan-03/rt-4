def test_gap_fill_pass():
    from backend.placement.placer import gap_fill_pass
    combined_placements = [
        {"insert_ms": 1000, "end_ms": 2000, "track": "major"},
        {"insert_ms": 12000, "end_ms": 13000, "track": "major"},
        {"insert_ms": 18000, "end_ms": 19000, "track": "minor"},
    ]
    fill_selections = [
        {
            "metadata": {
                "file_path": "fill1.mp3",
                "duration_ms": 1000,
            }
        }
    ]
    
    # Gap between 2000 and 12000 is 10000ms (>8000ms)
    # Gap between 13000 and 18000 is 5000ms (<=8000ms)
    
    gaps = gap_fill_pass(combined_placements, fill_selections, video_duration_ms=30000, min_gap_ms=8000)
    
    assert len(gaps) >= 1
    assert any(g["insert_ms"] == 2000 for g in gaps)
    assert not any(g["insert_ms"] == 13000 for g in gaps) # This gap is only 5000ms
    assert any(g["insert_ms"] == 19000 for g in gaps) # Gap from 19000 to 30000 is 11000ms
