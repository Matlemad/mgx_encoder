"""Provider factory — choose real vs mock providers with safe fallback.

Loads environment variables from `.env` (if present) and selects providers
based on PROVIDER_MODE and key availability:

- PROVIDER_MODE=mock  → always mock (offline)
- otherwise           → real provider when its API key is present, else mock

Real providers fall back to mock if they fail to configure, so the app never
breaks because of a missing/invalid key.
"""
from __future__ import annotations

import os
from typing import Any

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv optional
    pass

from .base import LyricsCorpusProvider, MusicAnalysisProvider, ProviderNotConfigured
from .mock_musixmatch import MockMusixmatch
from .mock_cyanite import MockCyanite


def _mode() -> str:
    return os.environ.get("PROVIDER_MODE", "mock").strip().lower()


def get_lyrics_provider() -> tuple[LyricsCorpusProvider, str]:
    """Return (provider, label). Label is 'musixmatch' or 'mock'."""
    if _mode() != "mock" and os.environ.get("MUSIXMATCH_API_KEY"):
        try:
            from .musixmatch import MusixmatchProvider

            return MusixmatchProvider(), "musixmatch"
        except ProviderNotConfigured:
            pass
        except Exception:  # noqa: BLE001 - never break the app on provider init
            pass
    return MockMusixmatch(), "mock"


def get_music_provider() -> tuple[MusicAnalysisProvider, str]:
    """Return (provider, label). Label is 'cyanite' or 'mock'."""
    if _mode() != "mock" and os.environ.get("CYANITE_API_KEY"):
        try:
            from .cyanite import CyaniteProvider  # type: ignore

            return CyaniteProvider(), "cyanite"
        except ProviderNotConfigured:
            pass
        except Exception:  # noqa: BLE001
            pass
    return MockCyanite(), "mock"


def provider_status() -> dict[str, Any]:
    """Lightweight status for UI banners (no network calls)."""
    mode = _mode()
    return {
        "mode": mode,
        "musixmatch": "live" if (mode != "mock" and os.environ.get("MUSIXMATCH_API_KEY")) else "mock",
        "cyanite": "live" if (mode != "mock" and os.environ.get("CYANITE_API_KEY")) else "mock",
    }
