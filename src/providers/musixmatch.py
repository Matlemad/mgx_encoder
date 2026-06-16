"""Real Musixmatch provider.

Uses the Musixmatch Pro API, primarily the **Analysis API**
(`track.lyrics.analysis.search`) which returns abstract, corpus-level data
(moods, themes, meaning, entities) — never raw lyrics. This aligns with the
project's copyright-safety rule.

COPYRIGHT SAFETY: this provider deliberately discards anything that could be a
literal lyric fragment (e.g. `themes[].quotes`). It only surfaces abstract
descriptors: theme names, moods, entity names/categories, and genres.

Auth: the API key is passed as the `apikey` query parameter on every call.
Requires MUSIXMATCH_API_KEY in the environment (loaded from .env).
"""
from __future__ import annotations

import os
from collections import Counter
from typing import Any

import requests

from .base import LyricsCorpusProvider, ProviderNotConfigured

_BASE_URL = "https://api.musixmatch.com/ws/1.1/"
_TIMEOUT = 25

# Canonical mood vocabulary accepted by the Analysis API (used to map free text).
_MOODS = [
    "Love", "Heartbreak", "Joy", "Empowerment", "Angst", "Reflection",
    "Inspiration", "Nostalgia", "Despair", "Celebration", "Anger", "Peace",
    "Solitude", "Adventure", "Social Commentary", "Hope", "Spirituality",
    "Freedom", "Party", "Nature",
]
_MOODS_LOWER = {m.lower(): m for m in _MOODS}


class MusixmatchProvider(LyricsCorpusProvider):
    """Real Musixmatch API provider (Analysis API + catalog search)."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("MUSIXMATCH_API_KEY", "")
        if not self.api_key:
            raise ProviderNotConfigured(
                "MUSIXMATCH_API_KEY not set. Add it to .env or set the environment variable."
            )
        self._session = requests.Session()

    # ── low-level helpers ────────────────────────────────────────────────────
    def _params(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        params = {"apikey": self.api_key}
        if extra:
            params.update(extra)
        return params

    @staticmethod
    def _unwrap(resp: requests.Response) -> dict[str, Any]:
        """Validate the Musixmatch envelope and return the `body` dict."""
        if resp.status_code == 401:
            raise ProviderNotConfigured("Musixmatch rejected the API key (401).")
        resp.raise_for_status()
        payload = resp.json().get("message", {})
        status = payload.get("header", {}).get("status_code")
        if status == 401:
            raise ProviderNotConfigured("Musixmatch rejected the API key (401).")
        if status == 403:
            raise ProviderNotConfigured("Musixmatch plan does not allow this endpoint (403).")
        if status != 200:
            raise RuntimeError(f"Musixmatch error (status {status}).")
        return payload.get("body", {}) or {}

    def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = self._session.get(_BASE_URL + endpoint, params=self._params(params), timeout=_TIMEOUT)
        return self._unwrap(resp)

    def _analysis_search(self, data: dict[str, Any], page_size: int = 10) -> list[dict[str, Any]]:
        resp = self._session.post(
            _BASE_URL + "track.lyrics.analysis.search",
            params=self._params({"page_size": min(100, page_size), "page": 1}),
            json={"data": data},
            timeout=_TIMEOUT,
        )
        body = self._unwrap(resp)
        return body.get("track_list", []) or []

    # ── abstract extraction (copyright-safe) ─────────────────────────────────
    @staticmethod
    def _track_genres(track: dict[str, Any]) -> list[str]:
        out: list[str] = []
        try:
            for g in track.get("primary_genres", {}).get("music_genre_list", []):
                name = g.get("music_genre", {}).get("music_genre_name")
                if name:
                    out.append(name)
        except Exception:  # noqa: BLE001
            pass
        return out

    def _aggregate_analysis(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Aggregate abstract descriptors across many tracks. No lyric text."""
        themes: Counter = Counter()
        moods: Counter = Counter()
        entities: Counter = Counter()
        genres: Counter = Counter()
        for it in items:
            analysis = it.get("analysis", {}) or {}
            for t in analysis.get("themes", {}).get("main_themes", []):
                name = t.get("theme")
                if name:
                    themes[name.lower()] += 1
            for m in analysis.get("moods", {}).get("main_moods", []):
                if m:
                    moods[m.lower()] += 1
            for e in analysis.get("entities", {}).get("entity_list", []):
                name = e.get("entity_name")
                if name:
                    entities[name.lower()] += 1
            for g in self._track_genres(it.get("track", {})):
                genres[g] += 1
        return {"themes": themes, "moods": moods, "entities": entities, "genres": genres}

    # ── public interface ─────────────────────────────────────────────────────
    def search_by_theme(self, themes: list[str], limit: int = 10) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for theme in themes:
            theme = (theme or "").strip()
            if not theme:
                continue
            data: dict[str, Any] = {}
            mapped_mood = _MOODS_LOWER.get(theme.lower())
            if mapped_mood:
                data["moods"] = [mapped_mood]
            else:
                data["themes"] = [theme[:500]]
            try:
                items = self._analysis_search(data, page_size=max(10, limit))
            except ProviderNotConfigured:
                raise
            except Exception:  # noqa: BLE001
                items = []
            agg = self._aggregate_analysis(items)
            assoc = [w for w, _ in agg["themes"].most_common(limit) if w != theme.lower()]
            assoc += [w for w, _ in agg["moods"].most_common(limit) if w not in assoc]
            results.append({
                "theme": theme,
                "corpus_associations": assoc[:limit],
                "related_moods": [w for w, _ in agg["moods"].most_common(5)],
                "common_genres": [g for g, _ in agg["genres"].most_common(5)],
                "n_tracks_analyzed": len(items),
                "source": "musixmatch_analysis",
                "note": "Abstract corpus patterns only — no lyrics.",
            })
        return results

    def related_artists(self, artist: str, limit: int = 5) -> list[str]:
        """Genre-based heuristic: Musixmatch has no direct 'related' endpoint.

        Resolve the artist's primary genre, then collect other artists with
        high-rated tracks in that genre. Returns artist names only (metadata).
        """
        artist = (artist or "").strip()
        if not artist:
            return []
        try:
            body = self._get("track.search", {
                "q_artist": artist, "page_size": 1, "page": 1, "s_track_rating": "desc",
            })
            tracks = body.get("track_list", [])
            if not tracks:
                return []
            genres = self._track_genres(tracks[0].get("track", {}))
            if not genres:
                return []
            body = self._get("track.search", {
                "q_track": genres[0], "page_size": 30, "page": 1, "s_track_rating": "desc",
            })
            names: list[str] = []
            for t in body.get("track_list", []):
                name = t.get("track", {}).get("artist_name")
                if name and name.lower() != artist.lower() and name not in names:
                    names.append(name)
            return names[:limit]
        except ProviderNotConfigured:
            raise
        except Exception:  # noqa: BLE001
            return []

    def artist_analysis_profile(self, artist: str, n_tracks: int = 5) -> dict[str, Any]:
        """Aggregate the abstract analysis of an artist's real top tracks.

        Grounds a reference profile in the artist's actual catalog while staying
        copyright-safe: only themes, moods, entities and genres are surfaced —
        never lyrics or literal quotes.
        """
        artist = (artist or "").strip()
        if not artist:
            return {"artist": artist, "themes": [], "moods": [], "entities": [], "genres": [],
                    "n_tracks_analyzed": 0, "source": "musixmatch_analysis"}
        body = self._get("track.search", {
            "q_artist": artist, "f_has_lyrics": 1, "s_track_rating": "desc",
            "page_size": min(40, max(5, n_tracks * 4)), "page": 1,
        })
        tracks = body.get("track_list", []) or []
        items: list[dict[str, Any]] = []
        a_lower = artist.lower()
        for t in tracks:
            if len(items) >= n_tracks:
                break
            track = t.get("track", {})
            # Keep only tracks actually credited to the queried artist (q_artist
            # can return loosely-matched / feature tracks).
            name = (track.get("artist_name") or "").lower()
            if name and a_lower not in name and name not in a_lower:
                continue
            ct = track.get("commontrack_id")
            if not ct:
                continue
            try:
                b = self._get("track.lyrics.analysis.get", {"commontrack_id": ct})
            except ProviderNotConfigured:
                raise
            except Exception:  # noqa: BLE001
                continue
            items.append({"track": track, "analysis": b.get("analysis", {}) or {}})
        agg = self._aggregate_analysis(items)
        return {
            "artist": artist,
            "themes": [w for w, _ in agg["themes"].most_common(10)],
            "moods": [w for w, _ in agg["moods"].most_common(6)],
            "entities": [w for w, _ in agg["entities"].most_common(8)],
            "genres": [g for g, _ in agg["genres"].most_common(5)],
            "n_tracks_analyzed": len(items),
            "source": "musixmatch_analysis",
        }

    def lexical_associations(self, word: str, limit: int = 10) -> list[dict[str, Any]]:
        word = (word or "").strip()
        if not word:
            return []
        try:
            items = self._analysis_search({"themes": [word[:500]]}, page_size=max(10, limit))
        except ProviderNotConfigured:
            raise
        except Exception:  # noqa: BLE001
            return []
        agg = self._aggregate_analysis(items)
        out: list[dict[str, Any]] = []
        for w, c in (agg["themes"] + agg["entities"]).most_common(limit + 1):
            if w == word.lower():
                continue
            out.append({"word": w, "co_frequency": c, "source": "musixmatch_analysis"})
            if len(out) >= limit:
                break
        return out

    def usage_patterns(self, word: str) -> list[dict[str, Any]]:
        word = (word or "").strip()
        if not word:
            return []
        try:
            items = self._analysis_search({"themes": [word[:500]]}, page_size=20)
        except ProviderNotConfigured:
            raise
        except Exception:  # noqa: BLE001
            return []
        agg = self._aggregate_analysis(items)
        patterns: list[dict[str, Any]] = []
        if agg["moods"]:
            top = ", ".join(m for m, _ in agg["moods"].most_common(3))
            patterns.append({"pattern": f"'{word}' frequently appears in songs with moods: {top}", "source": "musixmatch_analysis"})
        if agg["genres"]:
            top = ", ".join(g for g, _ in agg["genres"].most_common(3))
            patterns.append({"pattern": f"'{word}' is common in genres: {top}", "source": "musixmatch_analysis"})
        if agg["themes"]:
            top = ", ".join(t for t, _ in agg["themes"].most_common(3) if t != word.lower())
            if top:
                patterns.append({"pattern": f"'{word}' co-occurs with themes: {top}", "source": "musixmatch_analysis"})
        return patterns
