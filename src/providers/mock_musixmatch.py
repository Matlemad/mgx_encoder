"""Mock Musixmatch provider — realistic fake data, no copyrighted lyrics."""
from __future__ import annotations

import random
from typing import Any

from .base import LyricsCorpusProvider

_THEME_DB = {
    "love": ["heart", "kiss", "forever", "touch", "dream", "hold", "close", "fire"],
    "absence": ["distance", "memory", "light", "return", "shadow", "waiting", "empty", "gone"],
    "night": ["moon", "stars", "silence", "darkness", "sleep", "dream", "sky", "cold"],
    "movement": ["road", "running", "dance", "wind", "free", "flight", "steps", "journey"],
    "freedom": ["sky", "wings", "open", "wild", "road", "escape", "horizon", "air"],
    "pain": ["tears", "broken", "wound", "bleeding", "scar", "ache", "lost", "fall"],
    "hope": ["light", "tomorrow", "rise", "dawn", "believe", "wish", "new", "shine"],
    "city": ["street", "lights", "crowd", "noise", "rain", "neon", "concrete", "window"],
}

_ARTISTS_DB = {
    "default": ["Joni Mitchell", "Leonard Cohen", "Nick Drake", "Tom Waits", "Fiona Apple"],
    "pop": ["Billie Eilish", "Harry Styles", "Lorde", "The Weeknd", "Dua Lipa"],
    "soul": ["Marvin Gaye", "Stevie Wonder", "Aretha Franklin", "D'Angelo", "Erykah Badu"],
    "italian": ["Fabrizio De Andre", "Franco Battiato", "Lucio Dalla", "Mina", "Paolo Conte"],
}


class MockMusixmatch(LyricsCorpusProvider):
    """Returns plausible but fake corpus-level insights."""

    def search_by_theme(self, themes: list[str], limit: int = 10) -> list[dict[str, Any]]:
        results = []
        for theme in themes:
            key = theme.lower()
            associations = _THEME_DB.get(key, random.sample(list(_THEME_DB.get("love", [])), min(4, limit)))
            results.append({
                "theme": theme,
                "corpus_associations": associations[:limit],
                "frequency_rank": random.randint(50, 5000),
                "note": "Mock data — not from real corpus",
            })
        return results

    def related_artists(self, artist: str, limit: int = 5) -> list[str]:
        pool = _ARTISTS_DB.get("default", [])
        for cat in _ARTISTS_DB.values():
            if artist.lower() in [a.lower() for a in cat]:
                pool = cat
                break
        pool = [a for a in pool if a.lower() != artist.lower()]
        return pool[:limit]

    def lexical_associations(self, word: str, limit: int = 10) -> list[dict[str, Any]]:
        word_lower = word.lower()
        for theme, words in _THEME_DB.items():
            if word_lower in words or word_lower == theme:
                return [
                    {"word": w, "co_frequency": random.randint(10, 500), "source": "mock"}
                    for w in words[:limit] if w != word_lower
                ]
        generic = ["time", "way", "life", "world", "day", "place", "hand", "eye"]
        return [{"word": w, "co_frequency": random.randint(5, 200), "source": "mock"} for w in generic[:limit]]

    def usage_patterns(self, word: str) -> list[dict[str, Any]]:
        return [
            {"pattern": f"'{word}' often appears in opening lines of choruses", "confidence": 0.6, "source": "mock"},
            {"pattern": f"'{word}' frequently paired with spatial imagery", "confidence": 0.5, "source": "mock"},
            {"pattern": f"'{word}' used more in minor-key songs", "confidence": 0.4, "source": "mock"},
        ]
