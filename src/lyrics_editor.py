"""Lyrics editor: normalization, stanza detection, basic stats."""
from __future__ import annotations

import re
from collections import Counter
from typing import Any


def normalize_lyrics(text: str) -> str:
    """Clean up pasted lyrics: strip, collapse whitespace within lines."""
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        stripped = re.sub(r"[ \t]+", " ", stripped)
        cleaned.append(stripped)
    while cleaned and cleaned[-1] == "":
        cleaned.pop()
    while cleaned and cleaned[0] == "":
        cleaned.pop(0)
    return "\n".join(cleaned)


def split_lines(text: str) -> list[str]:
    return [l for l in text.splitlines() if l.strip()]


def detect_stanzas(text: str) -> list[list[str]]:
    """Split lyrics into stanzas separated by blank lines."""
    stanzas: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.strip() == "":
            if current:
                stanzas.append(current)
                current = []
        else:
            current.append(line.strip())
    if current:
        stanzas.append(current)
    return stanzas


def word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def line_count(text: str) -> int:
    return len(split_lines(text))


def stanza_count(text: str) -> int:
    return len(detect_stanzas(text))


def find_repeated_lines(text: str) -> list[dict[str, Any]]:
    """Find lines that appear more than once."""
    lines = [l.strip().lower() for l in text.splitlines() if l.strip()]
    counts = Counter(lines)
    return [
        {"line": line, "count": count}
        for line, count in counts.most_common()
        if count > 1
    ]


def most_common_words(text: str, top_n: int = 20) -> list[dict[str, Any]]:
    words = re.findall(r"\b\w+\b", text.lower())
    return [{"word": w, "count": c} for w, c in Counter(words).most_common(top_n)]


def rhyme_endings(text: str) -> list[str]:
    """Extract last syllable-like ending of each line (placeholder heuristic)."""
    endings = []
    for line in split_lines(text):
        words = re.findall(r"\b\w+\b", line)
        if words:
            last = words[-1].lower()
            ending = last[-3:] if len(last) >= 3 else last
            endings.append(ending)
    return endings


def analyze_lyrics(text: str) -> dict[str, Any]:
    """Run all lyrics stats and return a structured result."""
    normalized = normalize_lyrics(text)
    stanzas = detect_stanzas(normalized)
    return {
        "normalized_text": normalized,
        "n_lines": line_count(normalized),
        "n_stanzas": len(stanzas),
        "n_words": word_count(normalized),
        "stanzas": [[line for line in s] for s in stanzas],
        "repeated_lines": find_repeated_lines(normalized),
        "most_common_words": most_common_words(normalized),
        "rhyme_endings": rhyme_endings(normalized),
    }
