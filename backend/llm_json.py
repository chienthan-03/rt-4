import json
import logging
import re

logger = logging.getLogger(__name__)


def _strip_markdown_fence(raw: str) -> str:
    raw = raw.strip()
    if not raw.startswith("```"):
        return raw
    parts = raw.split("```")
    if len(parts) < 2:
        return raw
    inner = parts[1].strip()
    if inner.startswith("json"):
        inner = inner[4:].strip()
    return inner


def parse_llm_json(raw: str):
    """Parse JSON from an LLM response, tolerating markdown fences."""
    text = _strip_markdown_fence(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for pattern in (r"\{[\s\S]*\}", r"\[[\s\S]*\]"):
        match = re.search(pattern, text)
        if not match:
            continue
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            continue

    logger.warning("Failed to parse LLM JSON: %r", text[:200])
    raise json.JSONDecodeError("Could not parse LLM JSON", text, 0)
