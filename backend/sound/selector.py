import json
import logging

from openai import OpenAI
from backend.config import settings
from backend.llm_json import parse_llm_json
from backend.db.chroma import search_sounds
from backend.detection.highlight_detector import Highlight

logger = logging.getLogger(__name__)
_client = None

def get_client():
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url
        )
    return _client

FALLBACK_RULES = {
    "shock": "vine_boom",
    "fail": "metal_pipe",
    "sadness": "sad_violin",
    "hype": "crowd_cheer",
    "awkward": "bruh",
    "dramatic": "sad_violin",
}

def build_search_query(highlight: Highlight) -> str:
    return f"{highlight.event_type} {highlight.emotion} intensity={highlight.intensity:.1f}"

def apply_fallback_rule(emotion: str) -> dict | None:
    sound_name = FALLBACK_RULES.get(emotion)
    if not sound_name:
        return None
    return {"name": sound_name, "fallback": True}

def _filter_fresh_candidates(
    candidates: list[dict],
    used_sound_ids: set[str],
) -> list[dict]:
    if not used_sound_ids:
        return candidates
    fresh = [c for c in candidates if c["id"] not in used_sound_ids]
    return fresh if fresh else candidates


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
        f"({c['metadata'].get('emotion')}, intensity={c['metadata'].get('intensity', 0):.1f}, "
        f"type={c['metadata'].get('timing_type')})"
        for i, c in enumerate(candidates)
    ]
    prompt = f"""Chọn meme sound phù hợp nhất cho moment này:

HIGHLIGHT:
- Event: {highlight.event_type}
- Emotion: {highlight.emotion}
- Intensity: {highlight.intensity:.1f}/1.0
- Context: "{highlight.context_text}"

CANDIDATES:
{chr(10).join(items)}
{diversity_note}

Ưu tiên comedic timing và cultural fit với meme context.
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
    query = build_search_query(highlight)
    top_k = min(5 + len(used_sound_ids) * 2, 20)
    candidates = search_sounds(query, top_k=top_k)
    candidates = _filter_fresh_candidates(candidates, used_sound_ids)

    if not candidates:
        return apply_fallback_rule(highlight.emotion)

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
