import json
from openai import OpenAI
from backend.config import settings
from backend.db.chroma import search_sounds
from backend.detection.highlight_detector import Highlight

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

def llm_rerank(highlight: Highlight, candidates: list[dict]) -> dict:
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

Ưu tiên comedic timing và cultural fit với meme context.
Output JSON: {{"chosen_id": "...", "reason": "..."}}"""

    client = get_client()
    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

def select_sound(highlight: Highlight) -> dict | None:
    query = build_search_query(highlight)
    candidates = search_sounds(query, top_k=5)

    if not candidates:
        return apply_fallback_rule(highlight.emotion)

    if len(candidates) == 1:
        c = candidates[0]
        return {"chosen_id": c["id"], "metadata": c["metadata"]}

    result = llm_rerank(highlight, candidates)
    chosen_id = result["chosen_id"]
    meta = next((c["metadata"] for c in candidates if c["id"] == chosen_id), None)
    return {"chosen_id": chosen_id, "metadata": meta, "reason": result.get("reason")}
