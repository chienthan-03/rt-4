from unittest.mock import patch, MagicMock

def test_parse_whisper_response():
    from backend.signals.transcript import parse_whisper_segments
    mock_response = {
        "segments": [
            {"start": 0.0, "end": 1.5, "text": "oh no"},
            {"start": 2.0, "end": 3.0, "text": "what happened"}
        ]
    }
    segments = parse_whisper_segments(mock_response)
    assert len(segments) == 2
    assert segments[0]["text"] == "oh no"
    assert segments[0]["start_ms"] == 0

def test_keyword_score():
    from backend.signals.transcript import keyword_score
    assert keyword_score("oh no oh no") > 0.5
    assert keyword_score("the weather is nice") == 0.0

def test_transcribe_openrouter_json(monkeypatch, tmp_path):
    from backend.signals import transcript as tr
    wav = tmp_path / "dummy.wav"
    wav.write_bytes(b"RIFF")

    class FakeResp:
        def raise_for_status(self):
            return None
        def json(self):
            return {"text": "oh no"}

    monkeypatch.setattr(tr.requests, "post", lambda *a, **k: FakeResp())
    monkeypatch.setattr(tr, "_audio_duration_s", lambda _p: 2.0)
    result = tr.transcribe(str(wav))
    assert result["text"] == "oh no"
    assert len(result["segments"]) == 1
    assert result["skipped"] is False

def test_transcribe_skips_on_payment_required(monkeypatch, tmp_path):
    from backend.signals import transcript as tr
    wav = tmp_path / "dummy.wav"
    wav.write_bytes(b"RIFF")

    class FakeResp:
        status_code = 402
        def json(self):
            return {"error": {"message": "requires at least $0.50"}}

    def fake_post(*_a, **_k):
        resp = FakeResp()
        raise requests.HTTPError("402", response=resp)

    import requests
    monkeypatch.setattr(tr.requests, "post", fake_post)
    result = tr.transcribe(str(wav))
    assert result["skipped"] is True
    assert result["segments"] == []
