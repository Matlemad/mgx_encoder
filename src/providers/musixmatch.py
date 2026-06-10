"""Musixmatch provider stub — real API integration (not yet implemented)."""
from __future__ import annotations

import os
from typing import Any

from .base import LyricsCorpusProvider, ProviderNotConfigured


class MusixmatchProvider(LyricsCorpusProvider):
    """Real Musixmatch API provider.

    Requires MUSIXMATCH_API_KEY in environment or .env.

    Future methods will call:
    - track.search for theme-based corpus search
    - artist.related for related artists
    - Internal NLP for lexical associations and usage patterns
    """

    def __init__(self) -> None:
        self.api_key = os.environ.get("MUSIXMATCH_API_KEY", "")
        if not self.api_key:
            raise ProviderNotConfigured(
                "MUSIXMATCH_API_KEY not set. "
                "Add it to .env or set the environment variable."
            )

    def search_by_theme(self, themes: list[str], limit: int = 10) -> list[dict[str, Any]]:
        raise NotImplementedError("Musixmatch theme search not yet implemented")

    def related_artists(self, artist: str, limit: int = 5) -> list[str]:
        raise NotImplementedError("Musixmatch related artists not yet implemented")

    def lexical_associations(self, word: str, limit: int = 10) -> list[dict[str, Any]]:
        raise NotImplementedError("Musixmatch lexical associations not yet implemented")

    def usage_patterns(self, word: str) -> list[dict[str, Any]]:
        raise NotImplementedError("Musixmatch usage patterns not yet implemented")
