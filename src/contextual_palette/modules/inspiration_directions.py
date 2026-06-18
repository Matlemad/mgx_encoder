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

    # Combine the full Librettist context into focused directions.
    directions: list[str] = []

    # Prefer the unified Song Genome Summary (handles real + mock Cyanite),
    # falling back to raw MGX/Cyanite fields when absent.
    genome = context.get("song_genome_summary", {}) or {}
    mgx = context.get("mgx", {})
    harmony = mgx.get("H", {}) if isinstance(mgx, dict) else {}
    bpm = genome.get("bpm") or (mgx.get("R", {}) if isinstance(mgx, dict) else {}).get("bpm")
    mode = genome.get("mode") or harmony.get("key_mode") or harmony.get("mode")
    if bpm and bpm > 130:
        directions.append("Music is fast — short, image-dense lines will track the energy better than long sentences.")
    elif bpm and bpm < 80:
        directions.append("Music is slow — there is room to let a single image breathe across the phrase.")
    if mode == "minor":
        directions.append("Minor tonality invites understatement; let restraint carry the weight.")

    mood = genome.get("mood") or (context.get("cyanite", {}) or {}).get("mood_primary")
    if mood:
        directions.append(f"Music mood reads as '{mood}' — decide whether to align or contrast the lyric.")
    if genome.get("genres"):
        directions.append(f"Cyanite genre territory: {', '.join(genome['genres'][:3])} — lean in or subvert it.")

    # Vocal MIDI / Metric Fit awareness.
    vocal_midi = context.get("vocal_midi", {}) or {}
    metric_targets = context.get("metric_fit_targets", {}) or {}
    if vocal_midi.get("cadence_profile"):
        directions.append(f"Vocal melody cadence is {vocal_midi['cadence_profile']} — shape the last line to match.")
    if metric_targets.get("min_syllables") and metric_targets.get("max_syllables"):
        directions.append(
            f"Aim for ~{metric_targets['min_syllables']}–{metric_targets['max_syllables']} syllables per line "
            "to fit the melodic phrasing."
        )

    # Reference Profile (Musixmatch abstract) — copyright-safe direction only.
    ref = context.get("reference_profile", {})
    patterns = ref.get("abstract_patterns", {}) if isinstance(ref, dict) else {}
    reference_grounding = None
    if isinstance(ref, dict) and ref.get("artists"):
        reference_grounding = {
            "musixmatch_live": "Grounded in Musixmatch live abstract profile",
            "musixmatch_mock_fallback": "Based on mock profile (Musixmatch live failed)",
            "musixmatch_mock": "Based on mock corpus profile",
        }.get(ref.get("source"), "Based on reference profile")
    if patterns.get("narrative_stance"):
        directions.append(f"Reference stance is {patterns['narrative_stance']} — try a draft from that vantage point.")
    if patterns.get("common_themes"):
        directions.append(f"References recur around: {', '.join(patterns['common_themes'][:4])} — find your own angle on one.")

    brief = context.get("writing_brief", {})
    if brief.get("promising_images"):
        directions.append(f"From your brief: explore '{brief['promising_images'][0]}'.")

    import random
    prompts = random.sample(_PROMPTS, min(3, len(_PROMPTS)))

    return {
        "module": "inspiration_directions",
        "selected_text": text[:200],
        "reference_grounding": reference_grounding,
        "underexplored_territories": underexplored,
        "symbolic_opportunities": symbolic,
        "creative_directions": directions,
        "creative_prompts": prompts,
        "safety_note": "Creative directions only — not finished lyrics, and no copyrighted text is used.",
    }
