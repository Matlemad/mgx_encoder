"""Palette module: Hook Strength — evaluate chorus/hook potential."""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from ..selection_analyzer import SelectionType

id = "hook_strength"
title = "Hook Strength"
supported_types = [SelectionType.CHORUS, SelectionType.PHRASE]

_OPEN_VOWELS = set("aoàòáeèé")


def _words(text: str) -> list[str]:
    return re.findall(r"[a-zA-Zàèéìòù']+", text.lower())


def _vowel_openness(text: str) -> float:
    vowels = [c for c in text.lower() if c in "aeiouàèéìòù"]
    if not vowels:
        return 0.0
    open_count = sum(1 for v in vowels if v in _OPEN_VOWELS)
    return round(open_count / len(vowels), 2)


def run(text: str, context: dict[str, Any]) -> dict[str, Any]:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    words = _words(text)
    word_counts = Counter(words)

    strengths: list[str] = []
    weaknesses: list[str] = []
    moves: list[str] = []

    score = 50.0

    # Repetition is good for hooks.
    repeated = [w for w, c in word_counts.items() if c > 1 and len(w) > 2]
    if repeated:
        score += 12
        strengths.append(f"Repetition of '{repeated[0]}' aids memorability.")
    else:
        weaknesses.append("No repeated words — hooks usually lean on repetition.")

    # Line length: short, punchy lines hook better.
    avg_len = sum(len(l.split()) for l in lines) / max(1, len(lines))
    if avg_len <= 6:
        score += 10
        strengths.append("Short, punchy lines are easy to grab onto.")
    elif avg_len > 9:
        score -= 8
        weaknesses.append("Lines run long for a hook — consider tightening.")

    # Title-like phrase: a short standalone line.
    title_candidates = [l for l in lines if 1 <= len(l.split()) <= 5]
    if title_candidates:
        score += 8
        strengths.append("Contains a compact, title-like phrase.")

    # Vowel openness aids singability of a hook.
    openness = _vowel_openness(text)
    if openness >= 0.5:
        score += 8
        strengths.append("Open vowels make the hook easy to belt.")
    else:
        weaknesses.append("Mostly closed vowels — the hook may sing tight.")

    # Final word strength: avoid weak function endings.
    last_words = [l.split()[-1].lower() for l in lines if l.split()]
    weak_endings = {"the", "a", "and", "of", "to", "il", "la", "di", "e", "che"}
    if last_words and last_words[-1] in weak_endings:
        score -= 10
        weaknesses.append(f"Ends on a weak word ('{last_words[-1]}') — land on something resonant.")
        moves.append("Rework the final line so it ends on a strong, image-bearing word.")

    # Melody compatibility if MIDI present.
    vocal_midi = context.get("vocal_midi") or {}
    if vocal_midi.get("suggested_syllable_slots"):
        moves.append("Match the hook's syllable count to the vocal MIDI's phrase slots for a tight fit.")

    singability_notes = [
        f"Vowel openness: {openness} (>=0.5 is comfortable to sustain).",
    ]
    if not moves:
        moves.append("Consider a small melodic or lyrical 'turn' on the last line to make the hook land.")

    score = max(0, min(100, round(score)))

    return {
        "module": "hook_strength",
        "hook_score": score,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "title_candidates": title_candidates[:4],
        "singability_notes": singability_notes,
        "suggested_hook_moves": moves,
    }
