"""Abstract provider interfaces for external services."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ProviderNotConfigured(Exception):
    """Raised when a provider's API key is missing or invalid."""


class LyricsCorpusProvider(ABC):
    """Interface for lyric corpus services (e.g. Musixmatch)."""

    @abstractmethod
    def search_by_theme(self, themes: list[str], limit: int = 10) -> list[dict[str, Any]]:
        """Return corpus-level theme associations (no full lyrics)."""
        ...

    @abstractmethod
    def related_artists(self, artist: str, limit: int = 5) -> list[str]:
        """Return related artist names."""
        ...

    @abstractmethod
    def lexical_associations(self, word: str, limit: int = 10) -> list[dict[str, Any]]:
        """Return words frequently co-occurring with the given word in the corpus."""
        ...

    @abstractmethod
    def usage_patterns(self, word: str) -> list[dict[str, Any]]:
        """Return abstract usage patterns for a word across the corpus."""
        ...


class MusicAnalysisProvider(ABC):
    """Interface for music enrichment services (e.g. Cyanite)."""

    @abstractmethod
    def analyze_audio(self, audio_path: str) -> dict[str, Any]:
        """Return mood, genre, energy, valence, arousal, instrumentation."""
        ...

    @abstractmethod
    def similarity_tags(self, audio_path: str) -> list[str]:
        """Return descriptive similarity tags."""
        ...
