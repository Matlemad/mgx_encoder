"""Writing Brief generator (Lyrics Prompter — Mode B).

Given a free-text theme/concept, produce a structured, copyright-safe
*writing brief* that guides the songwriter. It NEVER generates complete
lyrics — only directions, scenes, lexical fields, and title seeds.

In mock mode this is heuristic and template-based. The same function can
later delegate to an LLM provider while keeping the output schema stable.
"""
from __future__ import annotations

import re
from typing import Any

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "about", "is", "are", "be", "i", "you", "it", "this", "that", "my", "your",
    "il", "lo", "la", "i", "gli", "le", "un", "una", "di", "a", "da", "in", "con",
    "su", "per", "che", "non", "mi", "ti", "si", "e", "o", "ma", "del", "della",
}

# Theme -> abstract creative scaffolding (copyright-safe, generic patterns).
_THEME_LIBRARY = {
    "love": {
        "scenes": ["a kitchen at dawn", "a phone left unanswered", "two coats on one hook"],
        "lexical": ["warmth", "proximity", "small habits", "hands", "thresholds"],
        "avoid": ["heart on fire", "you complete me", "love is a battlefield"],
        "promising": ["the dent your head leaves on the pillow", "a half-finished sentence"],
        "titles": ["The Space You Left", "Half a Sentence", "Two Coats"],
        "arc": ["closeness", "small fracture", "what remains"],
    },
    "loss": {
        "scenes": ["an empty chair at the table", "clothes that still smell of someone", "a voicemail you can't delete"],
        "lexical": ["absence", "weight", "silence", "objects", "rooms"],
        "avoid": ["forever in my heart", "gone too soon", "tears like rain"],
        "promising": ["the way a house gets louder when it's empty", "a kettle for one"],
        "titles": ["A Kettle for One", "Louder Empty", "Still Set for Two"],
        "arc": ["routine", "the missing", "acceptance or refusal"],
    },
    "city": {
        "scenes": ["a 3am bus stop", "rain on a neon sign", "a stranger's window lit up"],
        "lexical": ["concrete", "light", "movement", "anonymity", "noise"],
        "avoid": ["concrete jungle", "city of dreams", "lost in the lights"],
        "promising": ["the city breathing through subway grates", "a hundred lit windows, one of them yours"],
        "titles": ["Lit Windows", "3AM Bus", "Concrete Lullaby"],
        "arc": ["arrival", "dissolution into the crowd", "a single point of contact"],
    },
    "freedom": {
        "scenes": ["an open car window on a highway", "shoes left at a door", "a packed bag in the hallway"],
        "lexical": ["horizon", "speed", "open space", "shedding", "air"],
        "avoid": ["break these chains", "free as a bird", "spread my wings"],
        "promising": ["the moment the seatbelt sign turns off", "a bag you never unpack"],
        "titles": ["Seatbelt Sign", "Never Unpacked", "The Highway Window"],
        "arc": ["confinement", "decision", "motion"],
    },
    "time": {
        "scenes": ["a clock you stopped winding", "an old photo with the wrong date", "a calendar with no marks"],
        "lexical": ["repetition", "erosion", "memory", "routine", "change"],
        "avoid": ["time heals all wounds", "turn back time", "sands of time"],
        "promising": ["the way Tuesdays repeat", "a photograph aging faster than you"],
        "titles": ["The Clock I Stopped", "Tuesdays", "Wrong Date"],
        "arc": ["a fixed point", "drift", "return or release"],
    },
}

_POV_OPTIONS = [
    "first person, intimate (I/you)",
    "first person, retrospective (looking back)",
    "second person address (speaking to someone)",
    "third person observer (watching a scene)",
    "collective voice (we)",
]

_TEMPERATURE = ["warm and close", "cool and distant", "restless and tense", "calm and resigned", "bright and urgent"]


def _keywords(prompt: str) -> list[str]:
    words = re.findall(r"[a-zA-Zàèéìòù']+", prompt.lower())
    return [w for w in words if w not in _STOPWORDS and len(w) > 2]


def _match_theme(prompt: str) -> str:
    text = prompt.lower()
    synonyms = {
        "love": ["love", "amore", "lover", "romance", "kiss", "together"],
        "loss": ["loss", "grief", "death", "gone", "miss", "lutto", "perdita", "lasciare"],
        "city": ["city", "town", "street", "urban", "città", "metropoli", "strada"],
        "freedom": ["freedom", "free", "escape", "leave", "libertà", "fuga", "partire"],
        "time": ["time", "year", "old", "memory", "past", "tempo", "ricordo", "passato"],
    }
    best, best_score = "love", 0
    for theme, keys in synonyms.items():
        score = sum(text.count(k) for k in keys)
        if score > best_score:
            best, best_score = theme, score
    return best


def generate_writing_brief(
    theme_prompt: str,
    language: str = "auto",
    mgx_summary: dict[str, Any] | None = None,
    cyanite: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a structured, copyright-safe writing brief from a theme prompt."""
    prompt = (theme_prompt or "").strip()
    if not prompt:
        return {
            "core_theme": "",
            "point_of_view_options": [],
            "emotional_temperature": "",
            "possible_scenes": [],
            "lexical_fields": [],
            "images_to_avoid": [],
            "promising_images": [],
            "possible_titles": [],
            "chorus_concepts": [],
            "narrative_arc_options": [],
            "copyright_safe_note": "No prompt provided.",
        }

    theme_key = _match_theme(prompt)
    lib = _THEME_LIBRARY[theme_key]
    user_words = _keywords(prompt)

    # Blend music mood into emotional temperature when available.
    temperature = _TEMPERATURE[len(prompt) % len(_TEMPERATURE)]
    if cyanite and cyanite.get("mood_primary"):
        temperature = f"{temperature} (music reads as {cyanite['mood_primary']})"
    elif mgx_summary and mgx_summary.get("mode"):
        mode = mgx_summary.get("mode")
        bpm = mgx_summary.get("bpm", 0) or 0
        if mode == "minor" and bpm and bpm < 100:
            temperature = "subdued and reflective (slow minor music)"
        elif bpm and bpm > 130:
            temperature = "urgent and driving (fast tempo)"

    chorus_concepts = [
        f"A repeated image around '{user_words[0]}'" if user_words else "A single repeated image",
        f"A one-line refrain built on the title idea '{lib['titles'][0]}'",
        "A turn where the verse's question gets a partial answer",
    ]

    return {
        "core_theme": theme_key,
        "point_of_view_options": _POV_OPTIONS[:4],
        "emotional_temperature": temperature,
        "possible_scenes": lib["scenes"],
        "lexical_fields": list(dict.fromkeys(lib["lexical"] + user_words[:5])),
        "images_to_avoid": lib["avoid"],
        "promising_images": lib["promising"],
        "possible_titles": lib["titles"],
        "chorus_concepts": chorus_concepts,
        "narrative_arc_options": [
            " → ".join(lib["arc"]),
            " → ".join(reversed(lib["arc"])),
            "scene → detail → reversal",
        ],
        "copyright_safe_note": (
            "This brief contains only abstract directions and original seed images. "
            "It does not reproduce any existing song. The songwriter remains the author."
        ),
    }
