"""Select Tier 1 attention sounds for minor cues (no LLM)."""

from backend.config import settings
from backend.db.models import get_sounds, init_db
from backend.detection.minor_cues import MinorCue
from backend.sound.attention_map import ATTENTION_ALIASES, resolve_attention_alias
from backend.sound.library import find_sound_by_alias, sound_to_selection


def _attention_pool(db_path: str | None = None) -> list[dict]:
    db_path = db_path or settings.db_path
    init_db(db_path)
    return [s for s in get_sounds(db_path) if (s.get("tier") or "") == "attention"]


def _pick_from_pool(
    pool: list[dict],
    aliases: list[str],
    used_ids: set[str],
) -> dict | None:
    for alias in aliases:
        sound = find_sound_by_alias(alias)
        if sound and (sound.get("tier") or "") == "attention" and sound["id"] not in used_ids:
            return sound_to_selection(sound, reason="attention_map")

    for sound in pool:
        if sound["id"] not in used_ids:
            return sound_to_selection(sound, reason="attention_pool")

    return pool[0] if pool else None


def select_minor_sound(
    cue: MinorCue,
    used_sound_ids: set[str] | None = None,
) -> dict | None:
    used_sound_ids = used_sound_ids or set()
    pool = _attention_pool()
    if not pool:
        return None

    aliases = ATTENTION_ALIASES.get(cue.cue_type, ATTENTION_ALIASES["scene_change"])
    primary = resolve_attention_alias(cue.cue_type)
    ordered = ([primary] if primary else []) + [a for a in aliases if a != primary]
    return _pick_from_pool(pool, ordered, used_sound_ids)


def select_minor_sounds(cues: list[MinorCue]) -> list[dict | None]:
    used_ids: set[str] = set()
    selections: list[dict | None] = []
    for cue in cues:
        sel = select_minor_sound(cue, used_ids)
        if sel and sel.get("chosen_id"):
            used_ids.add(sel["chosen_id"])
        selections.append(sel)
    return selections
