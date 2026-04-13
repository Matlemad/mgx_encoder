"""Download audio from YouTube via yt-dlp with cookie support."""
from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

import yt_dlp


_YT_PATTERN = re.compile(
    r"(https?://)?(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[\w\-]+"
)

# Browsers to try for cookie extraction, in order of preference.
_COOKIE_BROWSERS = ["chrome", "firefox", "safari", "edge", "brave", "opera", "chromium"]


def is_valid_youtube_url(url: str) -> bool:
    return bool(_YT_PATTERN.match(url.strip()))


def _detect_cookie_browser() -> str | None:
    """Try each browser and return the first one that yt-dlp can read cookies from."""
    for browser in _COOKIE_BROWSERS:
        try:
            # Quick probe: extract_info with download=False to test cookie access
            with yt_dlp.YoutubeDL({"cookiesfrombrowser": (browser,), "quiet": True, "no_warnings": True}) as ydl:
                pass  # constructor succeeds → browser is available
            return browser
        except Exception:
            continue
    return None


def download_audio_from_youtube(
    url: str,
    output_dir: str | Path | None = None,
    cookies_from_browser: str | None = None,
    cookies_file: str | Path | None = None,
) -> dict[str, Any]:
    """Download audio from a YouTube URL.

    Authentication options (tried in order):
      1. ``cookies_file`` — path to a Netscape-format cookies.txt
      2. ``cookies_from_browser`` — browser name (e.g. "chrome", "firefox")
      3. Auto-detect: tries common browsers automatically

    Returns dict with keys: audio_path, title, duration.
    """
    url = url.strip()
    if not is_valid_youtube_url(url):
        raise ValueError(f"Invalid YouTube URL: {url}")

    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp())
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Clean previous downloads
    for old in output_dir.glob("yt_audio.*"):
        old.unlink(missing_ok=True)

    outtmpl = str(output_dir / "yt_audio.%(ext)s")

    ydl_opts: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }
        ],
        "quiet": True,
        "no_warnings": True,
    }

    # --- Cookie resolution ---
    if cookies_file:
        cf = Path(cookies_file)
        if cf.is_file():
            ydl_opts["cookiefile"] = str(cf)
    elif cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = (cookies_from_browser,)
    else:
        detected = _detect_cookie_browser()
        if detected:
            ydl_opts["cookiesfrombrowser"] = (detected,)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    title = info.get("title", "Unknown")
    duration = info.get("duration", 0)

    wav_path = output_dir / "yt_audio.wav"
    if not wav_path.exists():
        candidates = list(output_dir.glob("yt_audio.*"))
        if candidates:
            wav_path = candidates[0]
        else:
            raise RuntimeError("yt-dlp download succeeded but no audio file was found.")

    return {
        "audio_path": str(wav_path),
        "title": title,
        "duration": float(duration) if duration else 0.0,
    }
