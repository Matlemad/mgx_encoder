"""Cyanite provider — GraphQL connectivity + real audio analysis.

Cyanite exposes a GraphQL HTTP API at https://api.cyanite.ai/graphql.
Authentication is a Bearer integration access token (CYANITE_API_KEY).

Analysis flow (library file upload):
  1. fileUploadRequest        -> { id, uploadUrl }
  2. PUT the audio bytes to uploadUrl
  3. libraryTrackCreate(input: { uploadId, title })
        -> creates a LibraryTrack AND auto-enqueues AudioAnalysisV7
  4. poll libraryTrack(id) until audioAnalysisV7 is Finished / Failed
  5. read AudioAnalysisV7Finished.result (abstract descriptors only)

COPYRIGHT SAFETY: we only surface abstract descriptors (genre/mood/instrument
tags, energy/valence/arousal, key/bpm/time-signature, a caption). We never
store or expose lyrics or the audio itself.

Environment variables:
- CYANITE_API_KEY   : Bearer access token
- CYANITE_API_URL   : GraphQL endpoint (default https://api.cyanite.ai/graphql)
- CYANITE_MODE      : "graphql" to enable real calls; anything else = disabled
"""
from __future__ import annotations

import os
import time
from typing import Any, Callable

import requests

from .base import MusicAnalysisProvider, ProviderNotConfigured

_DEFAULT_URL = "https://api.cyanite.ai/graphql"
_TIMEOUT = 30
_UPLOAD_TIMEOUT = 300  # large audio files


# ── env helpers ──────────────────────────────────────────────────────────────
def _api_key() -> str:
    return os.environ.get("CYANITE_API_KEY", "").strip()


def _api_url() -> str:
    return (os.environ.get("CYANITE_API_URL") or _DEFAULT_URL).strip()


def _mode() -> str:
    return (os.environ.get("CYANITE_MODE") or "").strip().lower()


class CyaniteError(RuntimeError):
    """Transport / HTTP / GraphQL-level error with context."""


# ── reusable GraphQL request ─────────────────────────────────────────────────
def cyanite_graphql_request(
    query: str,
    variables: dict[str, Any] | None = None,
    *,
    timeout: int = _TIMEOUT,
) -> dict[str, Any]:
    """POST a GraphQL query to Cyanite and return the parsed JSON.

    Raises:
        ProviderNotConfigured: when CYANITE_API_KEY is missing or rejected (401/403).
        CyaniteError: on network errors, non-2xx HTTP, invalid JSON, or a GraphQL
            "errors" array.

    Returns the full parsed JSON dict (i.e. ``{"data": ...}``) on success.
    """
    api_key = _api_key()
    if not api_key:
        raise ProviderNotConfigured(
            "CYANITE_API_KEY not set. Add it to .env or set the environment variable."
        )

    url = _api_url()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    body: dict[str, Any] = {"query": query}
    if variables is not None:
        body["variables"] = variables

    try:
        resp = requests.post(url, json=body, headers=headers, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        raise CyaniteError(f"Network error contacting Cyanite ({url}): {exc}") from exc

    if resp.status_code == 401:
        raise ProviderNotConfigured("Cyanite rejected the access token (HTTP 401).")
    if resp.status_code == 403:
        raise ProviderNotConfigured("Cyanite token lacks permission for this request (HTTP 403).")
    if resp.status_code >= 400:
        snippet = (resp.text or "")[:500]
        raise CyaniteError(f"Cyanite HTTP {resp.status_code}: {snippet}")

    try:
        data = resp.json()
    except ValueError as exc:
        snippet = (resp.text or "")[:500]
        raise CyaniteError(f"Cyanite returned non-JSON response: {snippet}") from exc

    if isinstance(data, dict) and data.get("errors"):
        messages = "; ".join(
            str(e.get("message", e)) for e in data["errors"] if isinstance(e, dict)
        ) or str(data["errors"])
        raise CyaniteError(f"Cyanite GraphQL errors: {messages}")

    return data


def test_cyanite_credentials() -> dict[str, Any]:
    """Lightest possible GraphQL request to validate credentials (uses `ping`).

    Never raises: always returns a structured result so the UI can render it.
    Shape: {"ok": bool, "mode": str, "api_url": str, "message": str, "raw": dict|None}
    """
    mode = _mode()
    api_url = _api_url()

    if mode != "graphql":
        return {
            "ok": False, "mode": mode or "(unset)", "api_url": api_url,
            "message": "Cyanite is disabled (CYANITE_MODE is not 'graphql').",
            "raw": None,
        }
    if not _api_key():
        return {
            "ok": False, "mode": mode, "api_url": api_url,
            "message": "CYANITE_API_KEY is not set in the environment / .env.",
            "raw": None,
        }

    try:
        raw = cyanite_graphql_request("query { ping }")
    except ProviderNotConfigured as exc:
        return {"ok": False, "mode": mode, "api_url": api_url, "message": f"Auth error: {exc}", "raw": None}
    except CyaniteError as exc:
        return {"ok": False, "mode": mode, "api_url": api_url, "message": str(exc), "raw": None}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "mode": mode, "api_url": api_url, "message": f"Unexpected error: {exc}", "raw": None}

    return {
        "ok": True, "mode": mode, "api_url": api_url,
        "message": "Connected to Cyanite GraphQL (ping ok).", "raw": raw,
    }


# ── GraphQL documents ────────────────────────────────────────────────────────
_M_FILE_UPLOAD = "mutation { fileUploadRequest { id uploadUrl } }"

_M_TRACK_CREATE = """
mutation TrackCreate($input: LibraryTrackCreateInput!) {
  libraryTrackCreate(input: $input) {
    __typename
    ... on LibraryTrackCreateSuccess {
      createdLibraryTrack { id title }
      enqueueResult {
        __typename
        ... on LibraryTrackEnqueueError { message }
      }
    }
    ... on LibraryTrackCreateError { code message }
  }
}
""".strip()

# Abstract, copyright-safe descriptor selection.
_ANALYSIS_RESULT_FIELDS = """
genreTags
subgenreTags
moodTags
moodAdvancedTags
movementTags
characterTags
instrumentTags
voiceTags
energyLevel
emotionalProfile
valence
arousal
keyPrediction { value confidence }
bpmPrediction { value confidence }
bpmRangeAdjusted
timeSignature
musicalEraTag
predominantVoiceGender
voiceoverExists
transformerCaption
""".strip()

_Q_TRACK_ANALYSIS = """
query TrackAnalysis($id: ID!) {
  libraryTrack(id: $id) {
    __typename
    ... on LibraryTrack {
      id
      title
      audioAnalysisV7 {
        __typename
        ... on AudioAnalysisV7Finished {
          result { %s }
        }
      }
    }
    ... on LibraryTrackNotFoundError { message }
  }
}
""".strip() % _ANALYSIS_RESULT_FIELDS

_TERMINAL_OK = "AudioAnalysisV7Finished"
_TERMINAL_BAD = {"AudioAnalysisV7Failed", "AudioAnalysisV7NotAuthorized"}


# ── flow steps ───────────────────────────────────────────────────────────────
def request_file_upload() -> tuple[str, str]:
    """Return (file_id, upload_url) for a new file upload slot."""
    data = cyanite_graphql_request(_M_FILE_UPLOAD)["data"]["fileUploadRequest"]
    return data["id"], data["uploadUrl"]


def upload_file(upload_url: str, file_path: str) -> None:
    """PUT the raw audio bytes to the Cyanite-provided signed upload URL."""
    try:
        with open(file_path, "rb") as fh:
            resp = requests.put(upload_url, data=fh, timeout=_UPLOAD_TIMEOUT)
    except requests.exceptions.RequestException as exc:
        raise CyaniteError(f"File upload failed (network): {exc}") from exc
    if resp.status_code >= 400:
        raise CyaniteError(f"File upload failed (HTTP {resp.status_code}): {(resp.text or '')[:300]}")


def library_track_create(upload_id: str, title: str | None = None) -> str:
    """Create a LibraryTrack from an uploaded file. Returns the track id.

    Creating a track auto-enqueues AudioAnalysisV7.
    """
    variables = {"input": {"uploadId": upload_id, "title": title or "MGX upload"}}
    payload = cyanite_graphql_request(_M_TRACK_CREATE, variables)["data"]["libraryTrackCreate"]
    typename = payload.get("__typename")
    if typename == "LibraryTrackCreateError":
        raise CyaniteError(
            f"libraryTrackCreate error [{payload.get('code')}]: {payload.get('message')}"
        )
    track = payload.get("createdLibraryTrack") or {}
    track_id = track.get("id")
    if not track_id:
        raise CyaniteError(f"libraryTrackCreate returned no track id: {payload}")
    enq = payload.get("enqueueResult") or {}
    if enq.get("__typename") == "LibraryTrackEnqueueError":
        raise CyaniteError(f"Analysis enqueue failed: {enq.get('message')}")
    return track_id


def get_library_track_analysis(track_id: str) -> dict[str, Any]:
    """Fetch current analysis state for a track.

    Returns: {"status": <AudioAnalysisV7* typename>, "title": str|None,
              "result": dict|None, "raw": dict}
    """
    raw = cyanite_graphql_request(_Q_TRACK_ANALYSIS, {"id": track_id})
    node = (raw.get("data") or {}).get("libraryTrack") or {}
    if node.get("__typename") == "LibraryTrackNotFoundError":
        raise CyaniteError(f"Track not found: {track_id}")
    analysis = node.get("audioAnalysisV7") or {}
    status = analysis.get("__typename")
    result = analysis.get("result") if status == _TERMINAL_OK else None
    return {"status": status, "title": node.get("title"), "result": result, "raw": raw}


def normalize_analysis_result(result: dict[str, Any]) -> dict[str, Any]:
    """Reduce a raw AudioAnalysisV7Result into abstract, flat descriptors."""
    if not result:
        return {}
    key = result.get("keyPrediction") or {}
    bpm = result.get("bpmPrediction") or {}
    return {
        "genre_tags": result.get("genreTags") or [],
        "subgenre_tags": result.get("subgenreTags") or [],
        "mood_tags": result.get("moodTags") or [],
        "mood_advanced_tags": result.get("moodAdvancedTags") or [],
        "movement_tags": result.get("movementTags") or [],
        "character_tags": result.get("characterTags") or [],
        "instrument_tags": result.get("instrumentTags") or [],
        "voice_tags": result.get("voiceTags") or [],
        "energy_level": result.get("energyLevel"),
        "emotional_profile": result.get("emotionalProfile"),
        "valence": result.get("valence"),
        "arousal": result.get("arousal"),
        "key": {"value": key.get("value"), "confidence": key.get("confidence")} if key else None,
        "bpm": {"value": bpm.get("value"), "confidence": bpm.get("confidence")} if bpm else None,
        "bpm_range_adjusted": result.get("bpmRangeAdjusted"),
        "time_signature": result.get("timeSignature"),
        "musical_era": result.get("musicalEraTag"),
        "predominant_voice_gender": result.get("predominantVoiceGender"),
        "voiceover_exists": result.get("voiceoverExists"),
        "caption": result.get("transformerCaption"),
    }


def analyze_audio_file(
    file_path: str,
    title: str | None = None,
    *,
    poll_interval: float = 5.0,
    max_wait: float = 240.0,
    progress_cb: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Full local flow: upload -> create (auto-enqueue) -> poll -> result.

    Never raises: returns a structured dict so a UI can render success/error.
    Shape: {"ok": bool, "track_id": str|None, "status": str|None,
            "message": str, "analysis": dict|None, "raw": dict|None}
    """
    def _say(msg: str) -> None:
        if progress_cb:
            try:
                progress_cb(msg)
            except Exception:  # noqa: BLE001 - UI callback must never break the flow
                pass

    if _mode() != "graphql":
        return {"ok": False, "track_id": None, "status": None,
                "message": "Cyanite disabled (CYANITE_MODE != 'graphql').", "analysis": None, "raw": None}

    track_id = None
    try:
        _say("Requesting upload slot…")
        file_id, upload_url = request_file_upload()

        _say("Uploading audio…")
        upload_file(upload_url, file_path)

        _say("Creating track & enqueuing analysis…")
        track_id = library_track_create(file_id, title=title or os.path.basename(file_path))

        deadline = time.time() + max_wait
        last_status = None
        while True:
            state = get_library_track_analysis(track_id)
            status = state["status"]
            if status != last_status:
                _say(f"Analysis status: {status}")
                last_status = status

            if status == _TERMINAL_OK:
                analysis = normalize_analysis_result(state["result"] or {})
                return {"ok": True, "track_id": track_id, "status": status,
                        "message": "Analysis finished.", "analysis": analysis, "raw": state["raw"]}
            if status in _TERMINAL_BAD:
                return {"ok": False, "track_id": track_id, "status": status,
                        "message": f"Analysis ended with status {status}.", "analysis": None, "raw": state["raw"]}
            if time.time() >= deadline:
                return {"ok": False, "track_id": track_id, "status": status,
                        "message": f"Timed out after {int(max_wait)}s (last status: {status}). "
                                   f"Use the track id to fetch results later.",
                        "analysis": None, "raw": state["raw"]}
            time.sleep(poll_interval)
    except ProviderNotConfigured as exc:
        return {"ok": False, "track_id": track_id, "status": None, "message": f"Auth error: {exc}", "analysis": None, "raw": None}
    except CyaniteError as exc:
        return {"ok": False, "track_id": track_id, "status": None, "message": str(exc), "analysis": None, "raw": None}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "track_id": track_id, "status": None, "message": f"Unexpected error: {exc}", "analysis": None, "raw": None}


# ── provider class (used by the factory) ─────────────────────────────────────
class CyaniteProvider(MusicAnalysisProvider):
    """Real Cyanite API provider (library file analysis via GraphQL)."""

    def __init__(self) -> None:
        self.api_key = _api_key()
        if not self.api_key:
            raise ProviderNotConfigured(
                "CYANITE_API_KEY not set. Add it to .env or set the environment variable."
            )
        self.api_url = _api_url()

    def analyze_audio(self, audio_path: str) -> dict[str, Any]:
        out = analyze_audio_file(audio_path)
        if not out["ok"]:
            raise CyaniteError(out["message"])
        return out["analysis"] or {}

    def similarity_tags(self, audio_path: str) -> list[str]:
        # Derived from a fresh analysis would be wasteful; callers should use
        # analyze_audio() and read the *_tags fields. Kept minimal on purpose.
        raise NotImplementedError("Use analyze_audio(); similarity search not implemented yet.")
