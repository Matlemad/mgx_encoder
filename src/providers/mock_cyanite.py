"""Mock Cyanite provider — realistic fake music analysis data."""
from __future__ import annotations

import random
from typing import Any

from .base import MusicAnalysisProvider

_MOODS = ["melancholic", "euphoric", "dreamy", "aggressive", "peaceful", "tense", "nostalgic", "romantic"]
_GENRES = ["pop", "rock", "soul", "r&b", "electronic", "folk", "jazz", "hip-hop", "indie", "classical"]
_INSTRUMENTS = ["vocals", "piano", "guitar", "bass", "drums", "strings", "synth", "brass", "organ"]
_TAGS = [
    "driving beat", "atmospheric", "groovy", "anthemic", "intimate",
    "lo-fi", "cinematic", "uplifting", "dark", "funky", "acoustic",
    "layered vocals", "syncopated", "minimalist", "orchestral",
]


class MockCyanite(MusicAnalysisProvider):
    """Returns plausible but fake music enrichment data."""

    def analyze_audio(self, audio_path: str) -> dict[str, Any]:
        return {
            "mood_primary": random.choice(_MOODS),
            "mood_secondary": random.choice(_MOODS),
            "genre_primary": random.choice(_GENRES),
            "genre_secondary": random.choice(_GENRES),
            "energy": round(random.uniform(0.2, 0.9), 2),
            "valence": round(random.uniform(0.1, 0.9), 2),
            "arousal": round(random.uniform(0.2, 0.8), 2),
            "instrumentation": random.sample(_INSTRUMENTS, k=min(4, len(_INSTRUMENTS))),
            "note": "Mock data — not from real analysis",
        }

    def similarity_tags(self, audio_path: str) -> list[str]:
        return random.sample(_TAGS, k=min(5, len(_TAGS)))
