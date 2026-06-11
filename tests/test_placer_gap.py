def test_gap_fill_pass(tmp_path):
    from backend.placement.placer import gap_fill_pass

    fill_file = tmp_path / "fill1.mp3"
    fill_file.write_bytes(b"ID3")

    combined_placements = [
        {"insert_ms": 1000, "end_ms": 2000, "track": "major"},
        {"insert_ms": 12000, "end_ms": 13000, "track": "major"},
        {"insert_ms": 18000, "end_ms": 19000, "track": "minor"},
    ]
    fill_selections = [
        {
            "metadata": {
                "file_path": str(fill_file),
                "duration_ms": 1000,
            }
        },
        {
            "metadata": {
                "file_path": str(fill_file),
                "duration_ms": 1000,
            }
        },
    ]

    result = gap_fill_pass(
        combined_placements,
        fill_selections,
        total_duration_ms=30000,
        min_gap_ms=8000,
    )

    fillers = [p for p in result if p.get("track") == "filler"]
    assert len(fillers) >= 1
    assert any(2000 < f["insert_ms"] < 12000 for f in fillers)
    assert not any(13000 <= f["insert_ms"] < 18000 for f in fillers)
    assert any(f["insert_ms"] >= 19000 for f in fillers)
    assert len(result) == len(combined_placements) + len(fillers)


def test_gap_fill_ignores_exact_8000ms_gap(tmp_path):
    from backend.placement.placer import gap_fill_pass

    fill_file = tmp_path / "fill.mp3"
    fill_file.write_bytes(b"ID3")

    placements = [{"insert_ms": 0, "end_ms": 2000, "track": "major"}]
    result = gap_fill_pass(
        placements,
        [{"metadata": {"file_path": str(fill_file), "duration_ms": 500}}],
        total_duration_ms=10000,
        min_gap_ms=8000,
    )
    assert [p for p in result if p.get("track") == "filler"] == []
