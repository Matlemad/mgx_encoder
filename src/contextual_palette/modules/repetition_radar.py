"""Module 9: Repetition Radar — repeated words, symbols, dominant fields."""
from __future__ import annotations
import re
from collections import Counter
from typing import Any
from ..selection_analyzer import SelectionType

id = "repetition_radar"
title = "Repetition Radar"
supported_types = [SelectionType.STANZA, SelectionType.FULL_TEXT]

_STOPWORDS = {"i", "me", "my", "the", "a", "an", "is", "are", "was", "were", "it", "in", "on",
              "to", "of", "and", "or", "but", "that", "this", "for", "with", "you", "your",
              "il", "lo", "la", "le", "i", "gli", "un", "una", "di", "del", "della", "e", "o",
              "ma", "che", "non", "si", "mi", "ti", "ci", "per", "con", "su", "da", "al", "nel"}

_SYMBOL_KEYWORDS = {
    "light": ["light", "sun", "glow", "shine", "dawn", "luce", "sole", "bagliore", "alba"],
    "darkness": ["dark", "night", "shadow", "black", "buio", "notte", "ombra", "nero"],
    "water": ["rain", "sea", "tears", "wave", "river", "pioggia", "mare", "lacrime", "onda", "fiume"],
    "fire": ["fire", "burn", "flame", "heat", "fuoco", "bruciare", "fiamma", "calore"],
    "movement": ["walk", "run", "dance", "fly", "road", "cammino", "correre", "ballare", "volare", "strada"],
    "body": ["heart", "hand", "eye", "blood", "breath", "cuore", "mano", "occhio", "sangue", "respiro"],
}


def run(text: str, context: dict[str, Any]) -> dict[str, Any]:
    words = re.findall(r"\b\w+\b", text.lower())
    filtered = [w for w in words if w not in _STOPWORDS and len(w) > 2]
    freq = Counter(filtered)

    repeated = [{"word": w, "count": c} for w, c in freq.most_common(15) if c > 1]

    word_set = set(filtered)
    symbols = []
    for symbol, triggers in _SYMBOL_KEYWORDS.items():
        if word_set & set(triggers):
            symbols.append(symbol)

    mining = context.get("mining", {})
    fields = []
    for w, c in freq.most_common(5):
        fields.append(w)

    return {
        "repeated_words": repeated,
        "repeated_symbols": symbols,
        "dominant_fields": fields,
    }
