"""Cyanite provider stub — real API integration (not yet implemented)."""
from __future__ import annotations

import os
from typing import Any

from .base import MusicAnalysisProvider, ProviderNotConfigured


class CyaniteProvider(MusicAnalysisProvider):
    """Real Cyanite API provider.

    Requires CYANITE_API_KEY in environment or .env.

    Future methods will call Cyanite's GraphQL API for:
    - Audio analysis (mood, genre, energy, valence, arousal)
    - Instrumentation detection
    - Similarity search and tagging
    """

    def __init__(self) -> None:
        self.api_key = os.environ.get("CYANITE_API_KEY", "")
        if not self.api_key:
            raise ProviderNotConfigured(
                "CYANITE_API_KEY not set. "
                "Add it to .env or set the environment variable."
            )

    def analyze_audio(self, audio_path: str) -> dict[str, Any]:
        raise NotImplementedError("Cyanite audio analysis not yet implemented")

    def similarity_tags(self, audio_path: str) -> list[str]:
        raise NotImplementedError("Cyanite similarity tags not yet implemented")
