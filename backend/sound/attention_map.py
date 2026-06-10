"""Map minor cue types to attention-tier sound aliases."""

ATTENTION_ALIASES: dict[str, list[str]] = {
    "scene_change": ["whoosh-sfx", "whoosh", "woosh"],
    "transition": ["mouse-click", "click", "pop"],
    "silence_break": ["mouse-click", "click"],
}

ATTENTION_KEYWORDS = ("whoosh", "woosh", "pop", "click", "swipe", "ding", "ting", "swoosh")


def resolve_attention_alias(cue_type: str) -> str | None:
    aliases = ATTENTION_ALIASES.get(cue_type) or ATTENTION_ALIASES["scene_change"]
    return aliases[0] if aliases else None
