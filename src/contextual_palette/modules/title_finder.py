"""Palette module: Title Finder — suggest titles from the user's own text."""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from ..selection_analyzer import SelectionType

id = "title_finder"
title = "Title Finder"
supported_types = [SelectionType.STANZA, SelectionType.CHORUS, SelectionType.FULL_TEXT]

_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with",
    "is", "are", "be", "it", "this", "that", "i", "you", "we", "they", "my", "your",
    "il", "lo", "la", "i", "gli", "le", "un", "una", "di", "da", "in", "con", "su",
    "per", "che", "non", "mi", "ti", "si", "e", "o", "ma", "del", "della", "ho", "ha",
}


def _clean_phrase(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip(" .,!?;:\"'")).strip()


def run(text: str, context: dict[str, Any]) -> dict[str, Any]:
    lines = [_clean_phrase(l) for l in text.splitlines() if l.strip()]
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(t: str, source: str, reason: str) -> None:
        key = t.lower()
        if t and 1 <= len(t.split()) <= 6 and key not in seen:
            seen.add(key)
            candidates.append({"title": t, "source_line": source, "reason": reason})

    # 1) Short standalone lines make natural titles.
    for line in lines:
        if 1 <= len(line.split()) <= 5:
            add(line.title(), line, "Compact, self-contained line — reads as a title.")

    # 2) Repeated lines (likely the hook) are strong title seeds.
    line_counts = Counter(l.lower() for l in lines)
    for line in lines:
        if line_counts[line.lower()] > 1:
            add(line.title(), line, "Repeated line — already functions like a refrain.")

    # 3) Striking 2-3 word fragments built around salient content words.
    words = [w for w in re.findall(r"[a-zA-Zàèéìòù']+", text.lower()) if w not in _STOPWORDS and len(w) > 3]
    freq = Counter(words)
    for line in lines:
        toks = line.split()
        for i in range(len(toks) - 1):
            frag = " ".join(toks[i : i + 2])
            clean = _clean_phrase(frag)
            content = [t for t in re.findall(r"[a-zA-Zàèéìòù']+", clean.lower()) if t not in _STOPWORDS]
            if content and any(freq.get(c, 0) >= 1 for c in content):
                add(clean.title(), line, "Phrase containing a recurring image word.")
                break

    return {
        "module": "title_finder",
        "title_candidates": candidates[:8],
    }
