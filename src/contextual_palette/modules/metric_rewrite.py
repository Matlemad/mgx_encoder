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

_STYLES = [
    "conservative", "poetic", "symbolic", "concrete", "minimal",
    "narrative", "ironic", "darker", "simpler", "more_singable",
]

_DEFAULT_PRESERVE = {
    "syllable_count": True,
    "main_accents": True,
    "last_word": False,
    "rhyme": True,
    "meaning": True,
    "dominant_image": True,
    "emotional_tone": True,
}


def _what_changed(style: str, lexical_change: bool, length_change: int) -> str:
    base = {
        "conservative": "minimal substitution preserving tone",
        "poetic": "more lyrical word choice",
        "symbolic": "swapped toward symbolic register",
        "concrete": "replaced abstraction with a concrete image",
        "minimal": "trimmed to essentials",
        "narrative": "added narrative connective",
        "ironic": "introduced ironic distance",
        "darker": "shifted toward a darker tone",
        "simpler": "plainer, more direct phrasing",
        "more_singable": "favored open vowels for easier singing",
    }.get(style, "rephrased")
    if length_change > 0:
        base += f"; +{length_change} syllables"
    elif length_change < 0:
        base += f"; {length_change} syllables"
    return base


def run(text: str, context: dict[str, Any]) -> dict[str, Any]:
    controls = context.get("rewrite_controls", {}) or {}
    target_syllables = controls.get("target_syllables")
    # Optional single-style focus; otherwise produce a spread of styles.
    focus_style = controls.get("style")
    styles = [focus_style] if focus_style in _STYLES else _STYLES

    # Honor metric_fit rewrite targets if present in context (target syllables +
    # last-word / rhyme preservation). Explicit user controls win over these.
    metric_targets = context.get("metric_fit_targets") or {}
    preserve = {**_DEFAULT_PRESERVE}
    if "preserve_last_word" in metric_targets:
        preserve["last_word"] = bool(metric_targets["preserve_last_word"])
    if "preserve_rhyme" in metric_targets:
        preserve["rhyme"] = bool(metric_targets["preserve_rhyme"])
    preserve.update(controls.get("preserve") or {})

    if target_syllables is None and metric_targets:
        lo = metric_targets.get("min_syllables")
        hi = metric_targets.get("max_syllables")
        if lo and hi:
            target_syllables = round((lo + hi) / 2)

    original_syl = _estimate_syllables(text)
    original_words = _word_count(text)
    original_ending = _ending_type(text)
    words = text.split()

    alternatives = []
    warnings: list[str] = []

    for style in styles:
        new_words = list(words)
        lexical_change = False
        for i, w in enumerate(new_words):
            key = w.lower().strip(".,!?;:'\"")
            if key in _SYNONYM_MAP:
                syns = _SYNONYM_MAP[key]
                pick = syns[_STYLES.index(style) % len(syns)]
                if w[0].isupper():
                    pick = pick.capitalize()
                new_words[i] = pick
                lexical_change = True
                break

        if not lexical_change:
            if style in ("minimal", "simpler") and len(new_words) > 3:
                new_words = new_words[: len(new_words) - 1]
            elif style == "narrative" and len(new_words) > 1:
                new_words.insert(0, "And" if any(c.isascii() for c in text) else "E")
            else:
                continue

        # Respect last-word preservation.
        if preserve.get("last_word") and words and new_words and words[-1] != new_words[-1]:
            new_words[-1] = words[-1]

        alt_text = " ".join(new_words)
        alt_syl = _estimate_syllables(alt_text)
        length_change = alt_syl - original_syl

        ref = target_syllables if target_syllables else original_syl
        diff = abs(alt_syl - ref)
        if diff == 0:
            fit_note = "matches target syllable count"
        elif diff <= 1:
            fit_note = "within one syllable of target"
        else:
            fit_note = f"{diff} syllables off target ({ref})"

        alternatives.append({
            "text": alt_text,
            "estimated_syllables": alt_syl,
            "style": style,
            "what_changed": _what_changed(style, lexical_change, length_change),
            "fit_note": fit_note,
        })

    if not alternatives:
        warnings.append("No safe rewrites found for this selection — try a longer phrase.")
    if len(words) > 40:
        warnings.append("Selection is long; rewrites are limited to the selected phrase/stanza only.")

    return {
        "module": "metric_rewrite",
        "original_metrics": {
            "syllables": original_syl,
            "word_count": original_words,
            "ending_type": original_ending,
        },
        "target_syllables": target_syllables,
        "preserve": preserve,
        "alternatives": alternatives,
        "warnings": warnings,
    }
