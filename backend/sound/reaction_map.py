REACTION_ALIASES: dict[str, list[str]] = {
    "surprise": ["vine-boom"],
    "shock": ["vine-boom", "shocked"],
    "fail": ["bruh", "movie_1"],
    "awkward": ["huh", "mac-quack"],
    "cringe": ["huh", "faaah"],
    "plot_twist": ["dun-dun", "dramatic"],
    "dramatic": ["dun-dun", "dramatic"],
    "sadness": ["tf_nemesis", "sad violin"],
    "emotional": ["tf_nemesis"],
    "hype": ["10-diem", "anime-wow"],
    "win": ["10-diem", "ghe-chua"],
    "funny": ["baby-laughing", "thay-giao-ba-cuoi"],
}


def resolve_reaction_alias(highlight) -> str | None:
    keys = [highlight.audience_emotion, highlight.event_type, highlight.emotion]
    for key in keys:
        if not key:
            continue
        normalized = key.lower().replace(" ", "_")
        aliases = REACTION_ALIASES.get(normalized)
        if aliases:
            return aliases[0]
    return None
