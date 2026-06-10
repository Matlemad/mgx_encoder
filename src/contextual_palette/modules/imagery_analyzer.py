"""Module 7: Imagery Analyzer — sensory balance radar."""
from __future__ import annotations
from typing import Any
from ..selection_analyzer import SelectionType

id = "imagery_analyzer"
title = "Imagery Analyzer"
supported_types = [SelectionType.PHRASE, SelectionType.STANZA, SelectionType.FULL_TEXT]

_SENSORY_KEYWORDS = {
    "visual": [
        "light", "dark", "color", "shadow", "bright", "glow", "shine", "red", "blue", "green",
        "see", "watch", "look", "eye", "sight", "mirror", "reflect", "golden", "silver",
        "luce", "buio", "colore", "ombra", "brillante", "bagliore", "rosso", "blu", "verde",
        "vedere", "guardare", "occhio", "specchio", "oro", "argento",
    ],
    "auditory": [
        "sound", "voice", "song", "silence", "whisper", "scream", "echo", "noise", "music",
        "hear", "listen", "ring", "bell", "thunder", "drum",
        "suono", "voce", "canzone", "silenzio", "sussurro", "urlo", "eco", "rumore", "musica",
        "sentire", "ascoltare", "campana", "tuono", "tamburo",
    ],
    "tactile": [
        "touch", "cold", "warm", "soft", "hard", "skin", "hand", "finger", "rough", "smooth",
        "press", "hold", "grip", "caress", "burn", "freeze",
        "tocco", "freddo", "caldo", "morbido", "duro", "pelle", "mano", "dito", "liscio",
        "premere", "stringere", "accarezzare", "bruciare", "gelare",
    ],
    "spatial": [
        "far", "near", "above", "below", "inside", "outside", "deep", "high", "wide",
        "horizon", "edge", "center", "road", "path", "room", "sky", "ground",
        "lontano", "vicino", "sopra", "sotto", "dentro", "fuori", "profondo", "alto", "largo",
        "orizzonte", "bordo", "centro", "strada", "stanza", "cielo", "terra",
    ],
    "body": [
        "heart", "chest", "blood", "bone", "breath", "lungs", "stomach", "spine", "flesh",
        "head", "feet", "arms", "mouth", "lips",
        "cuore", "petto", "sangue", "ossa", "respiro", "polmoni", "stomaco", "carne",
        "testa", "piedi", "braccia", "bocca", "labbra",
    ],
}


def run(text: str, context: dict[str, Any]) -> dict[str, Any]:
    words = set(text.lower().split())
    scores = {}
    for sense, keywords in _SENSORY_KEYWORDS.items():
        count = len(words & set(keywords))
        scores[sense] = count

    total = sum(scores.values()) or 1
    normalized = {k: round(v / total, 2) for k, v in scores.items()}

    return normalized
