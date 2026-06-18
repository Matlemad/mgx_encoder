"""Reference Profile builder — copyright-safe abstraction of references.

Takes reference artists/songs and produces ONLY abstract, copyright-safe
patterns (themes, lexical fields, imagery density, narrative stance, etc.).
It never fetches, stores, or returns copyrighted lyrics. Uses the Musixmatch
provider abstraction (mock by default) for corpus-level signals.
"""
from __future__ import annotations

from typing import Any

_SAFE_RULES = [
    "Do not copy lyrics",
    "Do not imitate exact style",
    "Use only abstract patterns",
]

# Keys that could carry literal/copyrighted text from any provider response.
# Anything matching these is stripped before storing/displaying/exporting.
_LITERAL_TEXT_KEYS = {
    "lyrics", "lyrics_body", "lyrics_copyright", "snippet", "snippet_body",
    "quote", "quotes", "text", "excerpt", "body", "subtitle", "subtitle_body",
    "richsync", "richsync_body", "instrumental_text", "line", "lines",
}


def strip_literal_text(obj: Any) -> Any:
    """Recursively remove any keys that could contain literal/copyrighted text.

    Keeps only abstract descriptors (names, counts, tags). Used defensively so
    raw provider data can never leak lyrics/quotes into storage or the UI.
    """
    if isinstance(obj, dict):
        return {
            k: strip_literal_text(v)
            for k, v in obj.items()
            if k.lower() not in _LITERAL_TEXT_KEYS
        }
    if isinstance(obj, list):
        return [strip_literal_text(v) for v in obj]
    return obj

# Abstract stylistic fingerprints keyed by loose genre/register buckets.
# These are generic songwriting tendencies, not artist-specific content.
_REGISTER_PATTERNS = {
    "songwriter": {
        "imagery_density": "high — concrete objects carry emotion",
        "narrative_stance": "intimate first-person observer",
        "verse_style": "long, conversational lines that build a scene",
        "chorus_style": "understated, often a single resonant image",
        "symbolic_register": ["domestic objects", "weather", "rooms", "distance"],
        "typical_energy": "low to mid, dynamic restraint",
    },
    "pop": {
        "imagery_density": "low to mid — direct emotional statements",
        "narrative_stance": "second-person address (you)",
        "verse_style": "short, punchy setup lines",
        "chorus_style": "high-repetition hook with a clear title phrase",
        "symbolic_register": ["light", "bodies", "nights", "movement"],
        "typical_energy": "mid to high, strong dynamic lift into chorus",
    },
    "soul": {
        "imagery_density": "mid — sensual and warm",
        "narrative_stance": "confessional, communal call-and-response",
        "verse_style": "groove-led phrasing with melismatic space",
        "chorus_style": "repeated affirmations, room for vocal runs",
        "symbolic_register": ["fire", "warmth", "togetherness", "longing"],
        "typical_energy": "mid, deep pocket",
    },
    "italian_cantautore": {
        "imagery_density": "high — literary, narrative detail",
        "narrative_stance": "storyteller / third-person portraits",
        "verse_style": "dense, irregular meter serving the story",
        "chorus_style": "thematic refrain rather than a pop hook",
        "symbolic_register": ["streets", "sea", "social margins", "memory"],
        "typical_energy": "low to mid, lyric-forward",
    },
}

_ARTIST_REGISTER = {
    "joni mitchell": "songwriter", "leonard cohen": "songwriter", "nick drake": "songwriter",
    "tom waits": "songwriter", "fiona apple": "songwriter", "bob dylan": "songwriter",
    "billie eilish": "pop", "harry styles": "pop", "lorde": "pop", "the weeknd": "pop",
    "dua lipa": "pop", "taylor swift": "pop",
    "marvin gaye": "soul", "stevie wonder": "soul", "aretha franklin": "soul",
    "d'angelo": "soul", "erykah badu": "soul",
    "fabrizio de andre": "italian_cantautore", "franco battiato": "italian_cantautore",
    "lucio dalla": "italian_cantautore", "mina": "italian_cantautore", "paolo conte": "italian_cantautore",
}

_GENERIC = {
    "imagery_density": "mid — balance of statement and image",
    "narrative_stance": "first-person reflective",
    "verse_style": "regular lines establishing situation",
    "chorus_style": "memorable repeated phrase",
    "symbolic_register": ["light", "distance", "time", "movement"],
    "typical_energy": "mid",
}


def _register_for(artist: str) -> str:
    return _ARTIST_REGISTER.get(artist.strip().lower(), "")


def build_reference_profile(
    artists: list[str],
    provider: Any | None = None,
    reference_songs: list[str] | None = None,
    avoid_artists: list[str] | None = None,
    genre_tags: list[str] | None = None,
    lyrics_context: str = "",
    source: str = "musixmatch_mock",
    provider_status: dict[str, Any] | None = None,
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    """Create a copyright-safe abstract reference profile.

    `provider` is an optional LyricsCorpusProvider (mock by default) used only
    for corpus-level theme associations, never raw lyrics.

    `source` records provenance: "musixmatch_live" | "musixmatch_mock_fallback" |
    "musixmatch_mock". Output is sanitized of any literal text before return.
    """
    artists = [a.strip() for a in (artists or []) if a.strip()]
    avoid_artists = [a.strip() for a in (avoid_artists or []) if a.strip()]
    genre_tags = [t.strip() for t in (genre_tags or []) if t.strip()]

    registers = [r for r in (_register_for(a) for a in artists) if r]
    if not registers and genre_tags:
        for tag in genre_tags:
            tl = tag.lower()
            if tl in _REGISTER_PATTERNS:
                registers.append(tl)
            elif "pop" in tl:
                registers.append("pop")
            elif "soul" in tl or "r&b" in tl:
                registers.append("soul")

    # Blend matched registers into one abstract pattern set.
    blended = dict(_GENERIC)
    common_themes: list[str] = []
    lexical_fields: list[str] = []
    symbolic: list[str] = []

    if registers:
        # Pick the most common register as the spine.
        from collections import Counter

        spine = Counter(registers).most_common(1)[0][0]
        blended = dict(_REGISTER_PATTERNS[spine])
        for r in registers:
            symbolic.extend(_REGISTER_PATTERNS[r]["symbolic_register"])
        symbolic = list(dict.fromkeys(symbolic))

    # Artist-grounded abstraction: query the real catalog of the named artists
    # via the provider's Analysis API (abstract patterns only, no lyrics).
    from collections import Counter

    artist_profiles: list[dict[str, Any]] = []
    grounded_themes: Counter = Counter()
    grounded_moods: Counter = Counter()
    grounded_entities: Counter = Counter()
    grounded_genres: Counter = Counter()

    if provider is not None and hasattr(provider, "artist_analysis_profile") and artists:
        for artist in artists[:3]:  # cap API usage
            try:
                prof = provider.artist_analysis_profile(artist, n_tracks=5)
            except Exception:  # noqa: BLE001
                continue
            if not prof or not prof.get("n_tracks_analyzed"):
                continue
            artist_profiles.append(prof)
            grounded_themes.update(prof.get("themes", []))
            grounded_moods.update(prof.get("moods", []))
            grounded_entities.update(prof.get("entities", []))
            grounded_genres.update(prof.get("genres", []))

    grounded = bool(artist_profiles)

    # Corpus-level theme associations via provider (fallback / enrichment).
    if provider is not None:
        try:
            seed_themes = genre_tags or ["love", "night", "city"]
            corpus = provider.search_by_theme(seed_themes, limit=6)
            for entry in corpus:
                common_themes.append(entry.get("theme", ""))
                lexical_fields.extend(entry.get("corpus_associations", [])[:4])
        except Exception:  # noqa: BLE001
            pass

    if grounded:
        # Real artist data takes precedence in the abstraction.
        common_themes = [t for t, _ in grounded_themes.most_common(8)] + common_themes
        lexical_fields = (
            [t for t, _ in grounded_themes.most_common(10)]
            + [e for e, _ in grounded_entities.most_common(6)]
            + lexical_fields
        )
        symbolic = [e for e, _ in grounded_entities.most_common(8)] + symbolic

    common_themes = [t for t in dict.fromkeys(common_themes) if t]
    lexical_fields = list(dict.fromkeys(lexical_fields))
    symbolic = list(dict.fromkeys(symbolic))
    dominant_moods = [m for m, _ in grounded_moods.most_common(6)]

    creative_constraints = []
    if blended.get("chorus_style"):
        creative_constraints.append(f"Aim for a chorus that is {blended['chorus_style']}.")
    if blended.get("verse_style"):
        creative_constraints.append(f"Build verses that are {blended['verse_style']}.")
    if blended.get("imagery_density"):
        creative_constraints.append(f"Target imagery density: {blended['imagery_density']}.")
    if grounded and dominant_moods:
        creative_constraints.append(
            f"References' real catalog leans toward moods: {', '.join(dominant_moods[:4])}."
        )
    if grounded and common_themes:
        creative_constraints.append(
            f"Recurring themes in the references: {', '.join(common_themes[:5])}."
        )

    avoid = [f"Do not imitate the specific style of {a}." for a in avoid_artists]
    avoid.append("Avoid reproducing any recognizable melodic or lyrical phrase from references.")

    # If grounded in real catalog but caller passed a non-live source, upgrade it.
    if grounded and source == "musixmatch_mock":
        source = "musixmatch_live"

    profile = {
        "source": source,
        "provider_status": provider_status or {},
        "fallback_reason": fallback_reason,
        "copyright_safe": True,
        "stored_content_policy": "abstract_descriptors_only_no_lyrics",
        "artists": artists,
        "reference_songs": reference_songs or [],
        "grounded_in_real_catalog": grounded,
        "reference_artist_profiles": artist_profiles,
        "abstract_patterns": {
            "common_themes": common_themes or ["connection", "place", "change"],
            "lexical_fields": lexical_fields or blended.get("symbolic_register", []),
            "dominant_moods": dominant_moods,
            "genres": [g for g, _ in grounded_genres.most_common(6)],
            "imagery_density": blended.get("imagery_density", ""),
            "narrative_stance": blended.get("narrative_stance", ""),
            "typical_energy": blended.get("typical_energy", ""),
            "verse_style": blended.get("verse_style", ""),
            "chorus_style": blended.get("chorus_style", ""),
            "symbolic_register": symbolic or blended.get("symbolic_register", []),
        },
        "safe_inspiration_rules": list(_SAFE_RULES),
        "creative_constraints": creative_constraints,
        "avoid": avoid,
    }
    # Defensive: never let any literal/copyrighted text survive into storage.
    return strip_literal_text(profile)
