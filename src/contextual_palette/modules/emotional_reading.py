"""Module 4: Emotional Reading — compare lyrics emotion against music."""
from __future__ import annotations
from typing import Any
from ..selection_analyzer import SelectionType

id = "emotional_reading"
title = "Emotional Reading"
supported_types = [SelectionType.PHRASE, SelectionType.STANZA, SelectionType.FULL_TEXT]

_EMOTION_KEYWORDS = {
    "joy": ["happy", "joy", "smile", "laugh", "dance", "light", "shine", "bright",
            "felice", "gioia", "sorriso", "ridere", "ballare", "luce", "sole"],
    "sadness": ["sad", "cry", "tears", "alone", "gone", "empty", "lost", "dark",
                "triste", "piangere", "lacrime", "solo", "vuoto", "perso", "buio"],
    "anger": ["rage", "fire", "burn", "fight", "break", "scream", "storm",
              "rabbia", "fuoco", "bruciare", "lotta", "rompere", "urlare", "tempesta"],
    "hope": ["hope", "tomorrow", "rise", "dawn", "new", "believe", "dream",
             "speranza", "domani", "alba", "nuovo", "credere", "sogno"],
    "nostalgia": ["remember", "memory", "past", "once", "used to", "childhood",
                  "ricordo", "memoria", "passato", "infanzia", "ieri"],
    "desire": ["want", "need", "touch", "close", "body", "kiss", "hold",
               "voglio", "bisogno", "tocco", "vicino", "corpo", "bacio", "abbracciare"],
    "melancholy": ["rain", "grey", "window", "silence", "autumn", "fading",
                   "pioggia", "grigio", "finestra", "silenzio", "autunno", "svanire"],
}


def _detect_emotion(text: str) -> tuple[str, float]:
    words = set(text.lower().split())
    scores = {}
    for emotion, keywords in _EMOTION_KEYWORDS.items():
        score = len(words & set(keywords))
        if score > 0:
            scores[emotion] = score
    if not scores:
        return "neutral", 0.3
    best = max(scores, key=scores.get)
    conf = min(1.0, scores[best] / 3.0)
    return best, conf


def run(text: str, context: dict[str, Any]) -> dict[str, Any]:
    lyrics_emotion, lyrics_conf = _detect_emotion(text)

    mgx = context.get("mgx")
    cyanite = context.get("cyanite")

    music_emotion = "unknown"
    if cyanite:
        music_emotion = cyanite.get("mood_primary", "unknown")
    elif mgx:
        mode = mgx.get("H", {}).get("key_mode", mgx.get("H", {}).get("mode", ""))
        bpm = mgx.get("R", {}).get("bpm", 100)
        if mode == "minor" and bpm < 100:
            music_emotion = "melancholy"
        elif mode == "minor":
            music_emotion = "tension"
        elif bpm > 130:
            music_emotion = "energy"
        else:
            music_emotion = "warmth"

    _COMPAT = {
        ("joy", "energy"): 0.85, ("joy", "warmth"): 0.90, ("sadness", "melancholy"): 0.90,
        ("hope", "warmth"): 0.85, ("hope", "energy"): 0.70, ("nostalgia", "melancholy"): 0.85,
        ("anger", "tension"): 0.80, ("desire", "warmth"): 0.75, ("desire", "tension"): 0.65,
    }
    pair = (lyrics_emotion, music_emotion)
    alignment = _COMPAT.get(pair, _COMPAT.get((pair[1], pair[0]), 0.50))

    energy = None
    if cyanite:
        energy = cyanite.get("energy")
    section_role = context.get("section_role", "")

    notes = []
    if alignment < 0.5:
        notes.append(f"Lyrics read as '{lyrics_emotion}' but music suggests '{music_emotion}' — intentional contrast?")
    elif alignment < 0.7:
        notes.append(f"Moderate alignment between lyrics ({lyrics_emotion}) and music ({music_emotion}).")
    else:
        notes.append(f"Good alignment: both lyrics and music convey '{lyrics_emotion}' / '{music_emotion}'.")

    if energy is not None and lyrics_emotion in ("sadness", "melancholy", "nostalgia") and isinstance(energy, (int, float)) and energy > 0.6:
        notes.append("The emotional tone of the lyric is static/low while the music has high energy.")
    if section_role:
        notes.append(f"This is a '{section_role}' section — match its emotional function.")

    creative_options = [
        {
            "approach": "align with music",
            "suggestion": f"Lean the lyric further into '{music_emotion}' so words and sound reinforce each other.",
        },
        {
            "approach": "contrast against music intentionally",
            "suggestion": f"Keep the lyric '{lyrics_emotion}' against '{music_emotion}' music for productive tension.",
        },
        {
            "approach": "increase tension",
            "suggestion": "Introduce a contradictory image so the emotion is shown, not declared.",
        },
    ]

    return {
        "module": "emotional_reading",
        "lyrics_emotion": lyrics_emotion,
        "lyrics_confidence": round(lyrics_conf, 2),
        "music_emotion": music_emotion,
        "music_energy": energy,
        "section_role": section_role,
        "alignment_score": round(alignment, 2),
        "notes": notes,
        "creative_options": creative_options,
    }
