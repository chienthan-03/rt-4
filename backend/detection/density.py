from backend.detection.niche import DEFAULT_NICHE, get_niche_config


def max_major_sounds(video_duration_sec: float, niche: str = DEFAULT_NICHE) -> int:
    divisor = get_niche_config(niche)["major_divisor"]
    return max(1, int(video_duration_sec / divisor))


def apply_density_cap(highlights: list, video_duration_sec: float, niche: str = "entertainment") -> list:
    limit = max_major_sounds(video_duration_sec, niche)
    ranked = sorted(highlights, key=lambda h: h.impact_score, reverse=True)
    kept = ranked[:limit]
    return sorted(kept, key=lambda h: h.peak_ms)
