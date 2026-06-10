"""Detect selection type from highlighted text."""
from __future__ import annotations

from enum import Enum


class SelectionType(Enum):
    WORD = "word"
    PHRASE = "phrase"
    STANZA = "stanza"
    CHORUS = "chorus"
    FULL_TEXT = "full_text"


def classify_selection(text: str, full_lyrics: str = "") -> SelectionType:
    """Auto-detect what the user selected."""
    text = text.strip()
    if not text:
        return SelectionType.WORD

    lines = [l for l in text.splitlines() if l.strip()]
    words = text.split()

    if full_lyrics.strip() and text.strip() == full_lyrics.strip():
        return SelectionType.FULL_TEXT

    if len(lines) >= 3:
        lower = text.lower()
        chorus_hints = ["chorus", "ritornello", "hook", "refrain"]
        if any(h in lower for h in chorus_hints):
            return SelectionType.CHORUS
        return SelectionType.STANZA

    if len(lines) == 2:
        return SelectionType.STANZA

    if len(words) <= 1:
        return SelectionType.WORD

    return SelectionType.PHRASE
