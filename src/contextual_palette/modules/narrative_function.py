"""Module 8: Narrative Function — infer the role of a stanza."""
from __future__ import annotations
from typing import Any
from ..selection_analyzer import SelectionType

id = "narrative_function"
title = "Narrative Function"
supported_types = [SelectionType.STANZA, SelectionType.CHORUS]

_ROLE_KEYWORDS = {
    "observation": ["see", "watch", "look", "there", "outside", "window", "vedo", "guardo", "fuori", "finestra"],
    "conflict": ["but", "fight", "against", "struggle", "torn", "break", "ma", "lotta", "contro", "rompere"],
    "memory": ["remember", "once", "used to", "back then", "childhood", "ricordo", "quando", "ieri", "infanzia"],
    "desire": ["want", "need", "wish", "if only", "please", "voglio", "bisogno", "desidero", "se solo"],
    "revelation": ["now I know", "finally", "realize", "truth", "understand", "ora so", "finalmente", "capisco"],
    "transition": ["then", "suddenly", "meanwhile", "now", "and so", "poi", "improvvisamente", "intanto", "adesso"],
    "resolution": ["peace", "accept", "let go", "enough", "home", "rest", "pace", "accettare", "lasciare", "casa", "riposo"],
}


def run(text: str, context: dict[str, Any]) -> dict[str, Any]:
    lower = text.lower()
    scores = {}
    for role, keywords in _ROLE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in lower)
        if score > 0:
            scores[role] = score

    if not scores:
        return {"detected_role": "observation", "confidence": 0.2, "alternatives": list(_ROLE_KEYWORDS.keys())[:3]}

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_role = ranked[0][0]
    best_score = ranked[0][1]
    confidence = min(1.0, best_score / 3.0)
    alternatives = [r for r, _ in ranked[1:4]]

    return {"detected_role": best_role, "confidence": round(confidence, 2), "alternatives": alternatives}
