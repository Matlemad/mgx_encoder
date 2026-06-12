"""Palette module: Singability Check — flag hard-to-sing lines."""
from __future__ import annotations

import re
from typing import Any

from ..selection_analyzer import SelectionType

id = "singability_check"
title = "Singability Check"
supported_types = [SelectionType.PHRASE, SelectionType.CHORUS, SelectionType.STANZA]

_VOWELS = set("aeiouàèéìòùy")
_HARD_CONSONANTS = set("ptkbdgqx")
_PLOSIVES = set("ptkbdg")


def _consonant_clusters(word: str) -> list[str]:
    """Return runs of 3+ consecutive consonants (hard to articulate fast)."""
    clusters = re.findall(r"[^aeiouàèéìòù\s']{3,}", word.lower())
    return clusters


def run(text: str, context: dict[str, Any]) -> dict[str, Any]:
    letters = [c for c in text.lower() if c.isalpha()]
    vowels = [c for c in letters if c in _VOWELS]
    consonants = [c for c in letters if c not in _VOWELS]

    vowel_ratio = round(len(vowels) / max(1, len(letters)), 2)
    consonant_density = round(len(consonants) / max(1, len(letters)), 2)

    words = re.findall(r"[a-zA-Zàèéìòù']+", text)
    difficult: list[str] = []
    for w in words:
        clusters = _consonant_clusters(w)
        if clusters:
            difficult.append(w)

    plosive_count = sum(1 for c in letters if c in _PLOSIVES)
    plosive_ratio = round(plosive_count / max(1, len(letters)), 2)

    fast_note_warnings: list[str] = []
    vocal_midi = context.get("vocal_midi") or {}
    avg_note = vocal_midi.get("average_note_duration")
    if avg_note and avg_note < 0.25 and consonant_density > 0.55:
        fast_note_warnings.append(
            f"Short average notes (~{avg_note}s) + high consonant density: words may not articulate cleanly."
        )

    suggestions: list[str] = []
    score = 100.0
    if vowel_ratio < 0.35:
        score -= 25
        suggestions.append("Low vowel ratio — add open-vowel words for easier sustain.")
    if difficult:
        score -= min(30, 8 * len(difficult))
        suggestions.append(f"Consonant clusters in: {', '.join(difficult[:5])} — consider softer alternatives.")
    if plosive_ratio > 0.22:
        score -= 12
        suggestions.append("Many plosives (p/t/k/b/d/g) — may sound percussive or trip fast lines.")
    if not suggestions:
        suggestions.append("Line sits comfortably for singing.")

    score = max(0, min(100, round(score)))

    return {
        "module": "singability_check",
        "singability_score": score,
        "difficult_clusters": difficult[:8],
        "vowel_balance": {
            "vowel_ratio": vowel_ratio,
            "consonant_ratio": consonant_density,
            "plosive_ratio": plosive_ratio,
        },
        "consonant_density": consonant_density,
        "fast_note_warnings": fast_note_warnings,
        "suggestions": suggestions,
    }
