"""Module 5: Corpus Insights — abstract patterns from corpus (mock)."""
from __future__ import annotations
from typing import Any
from ..selection_analyzer import SelectionType

id = "corpus_insights"
title = "Corpus Insights"
supported_types = [SelectionType.WORD, SelectionType.PHRASE, SelectionType.STANZA]

_ASSOCIATIONS = {
    "night": {"common": ["moon", "stars", "silence", "cold"], "less_common": ["ink", "vertigo", "threshold"]},
    "notte": {"common": ["luna", "stelle", "silenzio", "freddo"], "less_common": ["inchiostro", "vertigine", "soglia"]},
    "love": {"common": ["heart", "forever", "kiss", "hold"], "less_common": ["gravity", "anchor", "frequency"]},
    "amore": {"common": ["cuore", "sempre", "bacio", "abbracciare"], "less_common": ["gravita", "ancora", "frequenza"]},
    "road": {"common": ["dust", "journey", "horizon", "travel"], "less_common": ["scar", "thread", "labyrinth"]},
    "strada": {"common": ["polvere", "viaggio", "orizzonte"], "less_common": ["cicatrice", "filo", "labirinto"]},
    "rain": {"common": ["window", "grey", "umbrella", "tears"], "less_common": ["percussion", "ink", "dissolution"]},
    "pioggia": {"common": ["finestra", "grigio", "ombrello", "lacrime"], "less_common": ["percussione", "dissoluzione"]},
    "fire": {"common": ["burn", "heat", "flame", "ash"], "less_common": ["hunger", "forge", "orbit"]},
    "fuoco": {"common": ["bruciare", "calore", "fiamma", "cenere"], "less_common": ["fame", "forgia", "orbita"]},
}


def run(text: str, context: dict[str, Any]) -> dict[str, Any]:
    words = text.strip().lower().split()
    common_all = []
    themes = []
    less_common_all = []

    for w in words:
        entry = _ASSOCIATIONS.get(w)
        if entry:
            common_all.extend(entry["common"])
            less_common_all.extend(entry["less_common"])
            themes.append(w)

    if not themes:
        musixmatch = context.get("musixmatch", {})
        for t in musixmatch.get("themes", []):
            common_all.extend(t.get("corpus_associations", [])[:3])
            themes.append(t.get("theme", ""))

    return {
        "common_associations": list(dict.fromkeys(common_all))[:10],
        "dominant_themes": list(dict.fromkeys(themes))[:5],
        "less_common_directions": list(dict.fromkeys(less_common_all))[:8],
    }
