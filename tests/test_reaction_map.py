from backend.detection.highlight_detector import Highlight
from backend.sound.reaction_map import resolve_reaction_alias


def test_surprise_maps_to_vine_boom():
    h = Highlight(
        0, 1000, 500, 0.8,
        event_type="shock",
        emotion="shock",
        audience_emotion="surprise",
    )
    assert resolve_reaction_alias(h) == "vine-boom"


def test_fail_maps_to_bruh():
    h = Highlight(0, 1000, 500, 0.8, event_type="fail", emotion="fail")
    assert resolve_reaction_alias(h) == "bruh"
