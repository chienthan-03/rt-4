IMPACT_MIN_MAJOR = 30


def compute_impact_score(importance: int, surprise: int, emotion_score: int) -> int:
    return max(1, importance) * max(1, surprise) * max(1, emotion_score)


def assign_sfx_tier(impact_score: int, has_punchline: bool) -> str:
    if impact_score >= 50 and has_punchline:
        return "comedy"
    return "emphasis"


def should_keep_highlight(impact_score: int) -> bool:
    return impact_score >= IMPACT_MIN_MAJOR


def apply_impact_fields(
    highlight,
    importance: int,
    surprise: int,
    emotion_score: int,
    has_punchline: bool,
    audience_emotion: str = "",
) -> None:
    impact = compute_impact_score(importance, surprise, emotion_score)
    highlight.importance = importance
    highlight.surprise = surprise
    highlight.emotion_score = emotion_score
    highlight.impact_score = impact
    highlight.has_punchline = has_punchline
    highlight.audience_emotion = audience_emotion
    highlight.sfx_tier = assign_sfx_tier(impact, has_punchline)
