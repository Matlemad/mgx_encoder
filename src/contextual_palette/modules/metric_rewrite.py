"""Module 3: Metric-Aware Rewrite — alternative phrasings preserving structure."""
from __future__ import annotations
import re
from typing import Any
from ..selection_analyzer import SelectionType

id = "metric_rewrite"
title = "Metric-Aware Rewrite"
supported_types = [SelectionType.PHRASE, SelectionType.STANZA]

_VOWELS = set("aeiouAEIOU")


def _estimate_syllables(text: str) -> int:
    """Approximate syllable count (works for IT and EN)."""
    words = re.findall(r"[a-zA-ZàèéìòùÀÈÉÌÒÙ]+", text.lower())
    count = 0
    for w in words:
        vowel_groups = re.findall(r"[aeiouàèéìòù]+", w)
        count += max(1, len(vowel_groups))
    return count


def _word_count(text: str) -> int:
    return len(text.split())


def _ending_type(text: str) -> str:
    words = re.findall(r"\w+", text)
    if not words:
        return "unknown"
    last = words[-1].lower()
    if last[-1:] in "aeiou":
        return "open"
    return "closed"


_SYNONYM_MAP = {
    "cammino": ["attraverso", "percorro", "procedo", "avanzo"],
    "walk": ["stride", "wander", "roam", "pace"],
    "luci": ["bagliori", "riflessi", "lampi", "chiarori"],
    "lights": ["glimmers", "beams", "glow", "flickers"],
    "città": ["metropoli", "borgo", "centro", "urbe"],
    "city": ["town", "streets", "downtown", "concrete"],
    "cuore": ["petto", "anima", "centro", "profondo"],
    "heart": ["chest", "core", "soul", "center"],
    "notte": ["buio", "sera", "ombra", "tenebre"],
    "night": ["dark", "evening", "midnight", "dusk"],
    "amore": ["affetto", "passione", "desiderio", "legame"],
    "love": ["devotion", "passion", "desire", "tenderness"],
}

_STYLES = ["conservative", "poetic", "symbolic", "concrete", "minimal", "narrative"]


def run(text: str, context: dict[str, Any]) -> dict[str, Any]:
    original_syl = _estimate_syllables(text)
    original_words = _word_count(text)
    original_ending = _ending_type(text)

    original_metrics = {
        "syllables": original_syl,
        "word_count": original_words,
        "ending_type": original_ending,
    }

    alternatives = []
    words = text.split()
    for style in _STYLES:
        new_words = list(words)
        changed = False
        for i, w in enumerate(new_words):
            key = w.lower().strip(".,!?;:'\"")
            if key in _SYNONYM_MAP:
                syns = _SYNONYM_MAP[key]
                pick = syns[_STYLES.index(style) % len(syns)]
                if w[0].isupper():
                    pick = pick.capitalize()
                new_words[i] = pick
                changed = True
                break

        if not changed:
            if style == "minimal" and len(new_words) > 3:
                new_words = new_words[:len(new_words) - 1]
            elif style == "narrative" and len(new_words) > 1:
                new_words.insert(0, "And" if any(c.isascii() for c in text) else "E")
            else:
                continue

        alt_text = " ".join(new_words)
        alt_syl = _estimate_syllables(alt_text)
        dist = abs(alt_syl - original_syl)
        alternatives.append({
            "text": alt_text,
            "syllables": alt_syl,
            "distance_score": dist,
            "style": style,
        })

    return {"original_metrics": original_metrics, "alternatives": alternatives}
