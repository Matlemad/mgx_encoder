"""Module 10: Inspiration Directions — final synthesis for creative prompts."""
from __future__ import annotations
from typing import Any
from ..selection_analyzer import SelectionType

id = "inspiration_directions"
title = "Inspiration Directions"
supported_types = [SelectionType.STANZA, SelectionType.FULL_TEXT]

_ALL_TERRITORIES = [
    "body", "silence", "memory", "architecture", "weather", "objects",
    "gravity", "texture", "distance", "rhythm", "light", "time",
    "corpo", "silenzio", "memoria", "architettura", "clima", "oggetti",
    "gravita", "distanza", "luce", "tempo",
]

_PROMPTS = [
    "Introduce a physical object that carries the emotional tension currently expressed abstractly.",
    "Replace one abstract noun with a concrete image the reader can see.",
    "Try a stanza where the speaker observes instead of feeling.",
    "What if the chorus contained a question instead of a statement?",
    "Consider a sensory detail — what does the scene smell, taste, or sound like?",
    "What happens if you remove the most repeated word? What fills the gap?",
    "Try rewriting one line from a different character's perspective.",
    "Add a line of silence — a pause, a breath, a blank space in the narrative.",
]


def run(text: str, context: dict[str, Any]) -> dict[str, Any]:
    words = set(text.lower().split())

    present = set()
    for territory in _ALL_TERRITORIES:
        if territory in words:
            present.add(territory)

    mining = context.get("mining", {})
    for w in list(mining.get("word_frequencies", {}).keys())[:10]:
        for territory in _ALL_TERRITORIES:
            if territory == w:
                present.add(territory)

    underexplored = [t for t in _ALL_TERRITORIES if t not in present][:6]

    imagery = context.get("imagery", {})
    low_senses = [sense for sense, score in imagery.items() if isinstance(score, (int, float)) and score < 0.1]
    symbolic = []
    if low_senses:
        symbolic.append(f"Underrepresented senses: {', '.join(low_senses)}. Try adding {low_senses[0]} imagery.")

    cliche = context.get("cliche", {})
    if cliche.get("cliche_score", 0) > 70:
        symbolic.append("High cliche density detected — consider replacing the flagged phrase with a more original image.")

    import random
    prompts = random.sample(_PROMPTS, min(3, len(_PROMPTS)))

    return {
        "underexplored_territories": underexplored,
        "symbolic_opportunities": symbolic,
        "creative_prompts": prompts,
    }
