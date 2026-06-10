"""Module 6: Cliche Detector — flag overused language."""
from __future__ import annotations
from typing import Any
from ..selection_analyzer import SelectionType

id = "cliche_detector"
title = "Cliche Detector"
supported_types = [SelectionType.PHRASE, SelectionType.STANZA]

_CLICHES = {
    "broken heart": (92, ["absence", "fracture", "silence", "hollow chest"]),
    "cuore spezzato": (90, ["assenza", "frattura", "silenzio", "petto vuoto"]),
    "tears falling": (85, ["salt traces", "water on stone", "dissolving"]),
    "lacrime che cadono": (84, ["tracce di sale", "acqua sulla pietra", "dissolversi"]),
    "light at the end": (88, ["first crack of dawn", "thin edge of morning", "opening"]),
    "luce in fondo": (87, ["primo spiraglio", "bordo sottile del mattino", "apertura"]),
    "dance in the rain": (91, ["stand in the storm", "let the water speak", "dissolve into weather"]),
    "fly away": (80, ["lift off the ground", "become weightless", "leave gravity behind"]),
    "forever and ever": (89, ["until the pattern breaks", "past every season", "beyond counting"]),
    "per sempre": (86, ["oltre ogni stagione", "fino a che il ritmo si spezza"]),
    "fire in my soul": (83, ["a furnace behind the ribs", "burning architecture", "heat without source"]),
    "fuoco nell'anima": (82, ["fornace dietro le costole", "calore senza origine"]),
    "follow your dreams": (95, ["build what you imagine", "chase the architecture in your head"]),
    "heart of gold": (87, ["generous marrow", "softness at the core", "unworn kindness"]),
    "lost in your eyes": (90, ["drowning in the lens", "pulled into focus", "absorbed"]),
    "take my breath away": (88, ["steal the air", "leave me gasping", "vacuum"]),
    "world on fire": (84, ["burning horizon", "scorched map", "ash geography"]),
}


def run(text: str, context: dict[str, Any]) -> dict[str, Any]:
    lower = text.strip().lower()
    best_score = 0
    reasons = []
    alternatives = []

    for cliche, (score, alts) in _CLICHES.items():
        if cliche in lower:
            if score > best_score:
                best_score = score
                reasons = [f"'{cliche}' is a widely overused phrase (score {score}/100)"]
                alternatives = alts

    if best_score == 0:
        words = lower.split()
        generic_pairs = [("my", "heart"), ("your", "love"), ("our", "time"), ("the", "night")]
        for a, b in generic_pairs:
            if a in words and b in words:
                best_score = max(best_score, 40)
                reasons.append(f"Generic pairing '{a} ... {b}' is common but not necessarily cliche")

    return {
        "cliche_score": best_score,
        "reasons": reasons if reasons else ["No obvious cliches detected"],
        "alternatives": alternatives,
    }
