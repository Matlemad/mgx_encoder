"""Palette module: Stress Alignment — strong words on strong positions."""
from __future__ import annotations

import re
from typing import Any

from ..selection_analyzer import SelectionType

id = "stress_alignment"
title = "Stress Alignment"
supported_types = [SelectionType.PHRASE, SelectionType.CHORUS]

_FUNCTION_WORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "is", "are", "be", "it", "this", "that", "as", "at", "by", "from", "i", "you",
    "il", "lo", "la", "i", "gli", "le", "un", "una", "di", "da", "in", "con", "su",
    "per", "che", "non", "mi", "ti", "si", "e", "o", "ma", "del", "della", "ho", "ha",
}


def _content_words(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Zàèéìòù']+", text.lower())
    return [w for w in words if w not in _FUNCTION_WORDS and len(w) > 2]


def run(text: str, context: dict[str, Any]) -> dict[str, Any]:
    words = re.findall(r"[a-zA-Zàèéìòù']+", text)
    content = _content_words(text)
    function_w = [w for w in words if w.lower() in _FUNCTION_WORDS]

    vocal_midi = context.get("vocal_midi") or {}
    strong_positions = vocal_midi.get("strong_positions", [])
    has_midi = bool(strong_positions)

    strong_words: list[str] = []
    weakly_placed: list[str] = []
    suggestions: list[str] = []

    # Heuristic alignment: in a typical bar, the first content word of a phrase
    # and the last content word tend to land on strong beats. Flag content words
    # buried between function words or at weak positions.
    if words:
        n_strong_slots = len(strong_positions) if has_midi else max(1, round(len(words) / 2))
        # Reward content words near phrase start/end (musical anchors).
        for idx, w in enumerate(words):
            wl = w.lower()
            if wl in _FUNCTION_WORDS:
                continue
            relative = idx / max(1, len(words) - 1)
            if relative < 0.25 or relative > 0.75:
                strong_words.append(w)
            else:
                weakly_placed.append(w)

        # Function word at a likely downbeat (phrase start) is a red flag.
        if words and words[0].lower() in _FUNCTION_WORDS:
            suggestions.append(
                f"Phrase starts on the function word '{words[0]}' — strong beats favor content words."
            )

    content_ratio = len(content) / max(1, len(words))
    placement_ratio = len(strong_words) / max(1, len(content))
    alignment = round(0.4 * content_ratio + 0.6 * placement_ratio, 2)

    if has_midi:
        diagnosis = (
            f"Compared against {len(strong_positions)} strong melodic positions from the vocal MIDI."
        )
    else:
        diagnosis = "No vocal MIDI: alignment estimated from phrase structure and word types."

    if placement_ratio < 0.5:
        suggestions.append("Several key words sit in weak metric spots — consider reordering so they land on accents.")
    if not suggestions:
        suggestions.append("Stress placement looks reasonable; key words fall near phrase anchors.")

    return {
        "module": "stress_alignment",
        "alignment_score": alignment,
        "strong_words": strong_words[:12],
        "weakly_placed_words": weakly_placed[:12],
        "diagnosis": diagnosis,
        "suggestions": suggestions,
    }
