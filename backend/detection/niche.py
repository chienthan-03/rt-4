"""Niche presets for major/minor SFX density."""

VALID_NICHES = frozenset({"entertainment", "edu", "lifestyle"})
DEFAULT_NICHE = "entertainment"

NICHE_CONFIG: dict[str, dict[str, int]] = {
    "entertainment": {"major_divisor": 5, "max_minor_per_window": 2},
    "edu": {"major_divisor": 8, "max_minor_per_window": 0},
    "lifestyle": {"major_divisor": 10, "max_minor_per_window": 1},
}

NICHE_LABELS: dict[str, str] = {
    "entertainment": "Giải trí",
    "edu": "Giáo dục",
    "lifestyle": "Lifestyle",
}


def normalize_niche(value: str | None) -> str:
    if not value:
        return DEFAULT_NICHE
    niche = value.strip().lower()
    if niche not in VALID_NICHES:
        raise ValueError(f"Invalid niche: {value}")
    return niche


def get_niche_config(niche: str) -> dict[str, int]:
    return NICHE_CONFIG.get(niche, NICHE_CONFIG[DEFAULT_NICHE])
