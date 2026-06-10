import json
import logging

from openai import OpenAI

from backend.config import settings
from backend.db.chroma import search_sounds
from backend.detection.highlight_detector import Highlight
from backend.llm_json import parse_llm_json
from backend.sound.library import find_sound_by_alias, resolve_fallback_sound, sound_to_selection
from backend.sound.reaction_map import resolve_reaction_alias

logger = logging.getLogger(__name__)
_client = None


def get_client():
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
    return _client


def build_search_query(highlight: Highlight) -> str:
    return (
        f"{highlight.event_type} {highlight.emotion} "
        f"tier={highlight.sfx_tier} intensity={highlight.intensity:.1f}"
    )


def _tier_matches(metadata: dict, sfx_tier: str) -> bool:
    return (metadata.get("tier") or "emphasis") == sfx_tier


def _filter_by_tier(candidates: list[dict], sfx_tier: str) -> list[dict]:
    tiered = [c for c in candidates if _tier_matches(c.get("metadata") or {}, sfx_tier)]
    return tiered if tiered else candidates


def apply_fallback_rule(emotion: str, sfx_tier: str = "emphasis") -> dict | None:
    sound = resolve_fallback_sound(emotion)
    if not sound:
        return None
    if (sound.get("tier") or "emphasis") != sfx_tier:
        return None
    return sound_to_selection(sound, reason="fallback_rule")


def _filter_fresh_candidates(
    candidates: list[dict],
    used_sound_ids: set[str],
) -> list[dict]:
    if not used_sound_ids:
        return candidates
    fresh = [c for c in candidates if c["id"] not in used_sound_ids]
    return fresh if fresh else candidates


def _try_reaction_map(highlight: Highlight) -> dict | None:
    alias = resolve_reaction_alias(highlight)
    if not alias:
        return None
    sound = find_sound_by_alias(alias)
    if not sound:
        return None
    if (sound.get("tier") or "emphasis") != highlight.sfx_tier:
        return None
    return sound_to_selection(sound, reason="reaction_map")


def llm_rerank(
    highlight: Highlight,
    candidates: list[dict],
    used_sound_ids: set[str] | None = None,
) -> dict:
    used_sound_ids = used_sound_ids or set()
    used_names = [
        c["metadata"].get("name", c["id"])
        for c in candidates
        if c["id"] in used_sound_ids
    ]
    diversity_note = ""
    if used_names:
        diversity_note = (
            f"\nĐÃ DÙNG TRONG VIDEO (ưu tiên chọn sound KHÁC, tránh lặp): "
            f"{', '.join(used_names)}"
        )

    items = [
        f"{i+1}. ID={c['id']} Name={c['metadata'].get('name')} "
        f"({c['metadata'].get('emotion')}, tier={c['metadata'].get('tier', 'emphasis')}, "
        f"intensity={c['metadata'].get('intensity', 0):.1f}, "
        f"type={c['metadata'].get('timing_type')})"
        for i, c in enumerate(candidates)
    ]
    prompt = f"""Chọn meme sound phù hợp nhất cho moment này:

HIGHLIGHT:
- Event: {highlight.event_type}
- Emotion: {highlight.emotion}
- SFX Tier: {highlight.sfx_tier} (emphasis=comedic emphasis, comedy=funny punchline)
- Impact: {highlight.impact_score}
- Intensity: {highlight.intensity:.1f}/1.0
- Context: "{highlight.context_text}"

CANDIDATES:
{chr(10).join(items)}
{diversity_note}

Ưu tiên comedic timing và cultural fit với meme context.
Chỉ chọn sound phù hợp tier {highlight.sfx_tier}.
Đa dạng sound — không lặp cùng một meme nếu có lựa chọn khác hợp lý.
Chỉ trả về JSON hợp lệ, không markdown: {{"chosen_id": "...", "reason": "ngắn gọn"}}"""

    client = get_client()
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=512,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content or ""
    return parse_llm_json(raw)


def select_sound(
    highlight: Highlight,
    used_sound_ids: set[str] | None = None,
) -> dict | None:
    used_sound_ids = used_sound_ids or set()

    reaction = _try_reaction_map(highlight)
    if reaction and reaction["chosen_id"] not in used_sound_ids:
        return reaction

    query = build_search_query(highlight)
    top_k = min(5 + len(used_sound_ids) * 2, 20)
    candidates = search_sounds(query, top_k=top_k)
    candidates = _filter_by_tier(candidates, highlight.sfx_tier)
    candidates = _filter_fresh_candidates(candidates, used_sound_ids)

    if not candidates:
        return apply_fallback_rule(highlight.emotion, highlight.sfx_tier)

    if len(candidates) == 1:
        c = candidates[0]
        return {"chosen_id": c["id"], "metadata": c["metadata"]}

    try:
        result = llm_rerank(highlight, candidates, used_sound_ids)
        chosen_id = result.get("chosen_id")
        if not chosen_id:
            raise ValueError("missing chosen_id")
        if chosen_id in used_sound_ids:
            fresh = _filter_fresh_candidates(candidates, used_sound_ids)
            if fresh:
                c = fresh[0]
                return {
                    "chosen_id": c["id"],
                    "metadata": c["metadata"],
                    "reason": "diversity_fallback",
                }
        meta = next((c["metadata"] for c in candidates if c["id"] == chosen_id), None)
        if meta is None:
            raise ValueError(f"unknown chosen_id: {chosen_id}")
        return {"chosen_id": chosen_id, "metadata": meta, "reason": result.get("reason")}
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        logger.warning("LLM rerank failed (%s), using top fresh candidate", e)
        c = candidates[0]
        return {"chosen_id": c["id"], "metadata": c["metadata"], "reason": "vector_search_fallback"}


def select_sounds(highlights: list[Highlight]) -> list[dict | None]:
    """Pick a sound per highlight, avoiding repeats when possible."""
    used_sound_ids: set[str] = set()
    selections: list[dict | None] = []
    for highlight in highlights:
        selection = select_sound(highlight, used_sound_ids)
        if selection and selection.get("chosen_id"):
            used_sound_ids.add(selection["chosen_id"])
        selections.append(selection)
    return selections
