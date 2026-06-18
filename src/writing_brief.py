"""Writing Brief generator (Lyrics Prompter — Mode B).

Given a free-text theme/concept, produce a structured, copyright-safe
*writing brief* that guides the songwriter. It NEVER generates complete
lyrics — only directions, scenes, lexical fields, and title seeds.

In mock mode this is heuristic and template-based. The same function can
later delegate to an LLM provider while keeping the output schema stable.
"""
from __future__ import annotations

import json
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


_BRIEF_KEYS = [
    "core_theme", "point_of_view_options", "emotional_temperature", "possible_scenes",
    "lexical_fields", "images_to_avoid", "promising_images", "possible_titles",
    "chorus_concepts", "narrative_arc_options",
]

_AI_SYSTEM = (
    "You are a songwriting development editor. From a theme/concept you produce a "
    "structured, ORIGINAL, copyright-safe WRITING BRIEF — directions only, never full lyrics, "
    "never quoting existing songs. Be specific to the given prompt (use its own nouns and imagery), "
    "and propose fresh, concrete images rather than clichés. Output STRICT JSON only."
)


def _parse_json(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None
    text = re.sub(r"^```(?:json)?", "", raw.strip()).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:  # noqa: BLE001
                return None
    return None


def _ai_writing_brief(
    prompt: str,
    language: str,
    mgx_summary: dict[str, Any] | None,
    cyanite: dict[str, Any] | None,
    provider: Any,
    reference_profile: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """LLM-grounded brief tailored to the actual prompt. Returns None on failure."""
    music_bits = []
    if cyanite and cyanite.get("mood_primary"):
        music_bits.append(f"music mood: {cyanite['mood_primary']}")
    if mgx_summary:
        if mgx_summary.get("mode"):
            music_bits.append(f"key mode: {mgx_summary['mode']}")
        if mgx_summary.get("bpm"):
            music_bits.append(f"tempo: {mgx_summary['bpm']} BPM")
    music_ctx = ("; ".join(music_bits)) or "n/a"

    # Abstract reference direction (Musixmatch) — inspiration only, never imitation.
    ref_line = ""
    rp = reference_profile or {}
    patterns = rp.get("abstract_patterns", {}) if isinstance(rp, dict) else {}
    if patterns:
        bits = []
        if patterns.get("common_themes"):
            bits.append(f"recurring themes: {', '.join(patterns['common_themes'][:5])}")
        if patterns.get("dominant_moods"):
            bits.append(f"moods: {', '.join(patterns['dominant_moods'][:4])}")
        if patterns.get("narrative_stance"):
            bits.append(f"narrative stance: {patterns['narrative_stance']}")
        if bits:
            ref_line = (
                "\nAbstract reference direction (inspiration ONLY — never imitate specific lines, "
                f"derived from Musixmatch analysis): {'; '.join(bits)}.\n"
            )

    user = (
        f"THEME / CONCEPT (write the brief specifically about this): \"\"\"{prompt[:1200]}\"\"\"\n"
        f"Language for all text: {language}.\n"
        f"Musical context to honour in tone: {music_ctx}.\n"
        f"{ref_line}\n"
        "Return STRICT JSON with EXACTLY these keys:\n"
        "{\n"
        '  "core_theme": short phrase capturing the concept,\n'
        '  "emotional_temperature": one vivid phrase,\n'
        '  "point_of_view_options": [3 distinct POV options],\n'
        '  "possible_scenes": [3 concrete original scenes tied to the prompt],\n'
        '  "lexical_fields": [6-8 word fields/registers],\n'
        '  "images_to_avoid": [4-5 clichés to avoid for this theme],\n'
        '  "promising_images": [3 fresh concrete images],\n'
        '  "possible_titles": [3 original title ideas],\n'
        '  "chorus_concepts": [2 chorus ideas, described not written],\n'
        '  "narrative_arc_options": [3 short arcs like "a -> b -> c"]\n'
        "}\n"
        "No commentary. JSON object only. Do NOT write any full lyric lines."
    )
    try:
        raw = provider.generate(user, system=_AI_SYSTEM, max_tokens=700, temperature=0.7)
    except Exception:  # noqa: BLE001
        return None
    data = _parse_json(raw)
    if not isinstance(data, dict):
        return None
    # Validate the essential keys are present and non-trivial.
    if not data.get("core_theme") or not data.get("possible_scenes"):
        return None
    out = {k: data.get(k, []) for k in _BRIEF_KEYS}
    out["core_theme"] = str(data.get("core_theme", "")).strip()
    out["emotional_temperature"] = str(data.get("emotional_temperature", "")).strip()
    out["source"] = "ai"
    out["copyright_safe_note"] = (
        "AI-generated brief: abstract directions and original seed images only. "
        "No existing song is reproduced. The songwriter remains the author."
    )
    return out


def generate_writing_brief(
    theme_prompt: str,
    language: str = "auto",
    mgx_summary: dict[str, Any] | None = None,
    cyanite: dict[str, Any] | None = None,
    provider: Any | None = None,
    reference_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a structured, copyright-safe writing brief from a theme prompt.

    If a live LLM `provider` is supplied, the brief is generated by the model and
    tailored to the actual prompt (grounded in the abstract `reference_profile`
    when present); otherwise a heuristic template is used.
    """
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

    # Prefer an AI-grounded brief when a live LLM provider is available.
    if provider is not None and getattr(provider, "is_live", False):
        ai = _ai_writing_brief(prompt, language, mgx_summary, cyanite, provider, reference_profile)
        if ai:
            return ai

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
        "source": "heuristic",
        "copyright_safe_note": (
            "This brief contains only abstract directions and original seed images. "
            "It does not reproduce any existing song. The songwriter remains the author."
        ),
    }
