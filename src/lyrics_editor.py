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


# --------------------------------------------------------------------------- #
# Prosody / syllable estimation (IT + EN heuristic)
# --------------------------------------------------------------------------- #

_VOWELS_IT = "aeiouàèéìòùy"
_VOWELS_EN = "aeiouy"

# English-ish markers vs Italian-ish markers for language auto-detection.
_IT_HINTS = {"che", "non", "per", "con", "sono", "una", "del", "della", "mi", "ti", "ci", "gli", "più", "perché", "così"}
_EN_HINTS = {"the", "and", "you", "your", "with", "this", "that", "are", "was", "for", "don't", "i'm", "we're"}


def detect_language(text: str) -> str:
    words = set(re.findall(r"[a-zàèéìòù']+", text.lower()))
    it = len(words & _IT_HINTS)
    en = len(words & _EN_HINTS)
    if it > en:
        return "it"
    if en > it:
        return "en"
    return "en"


def _count_syllables_it(word: str) -> int:
    """Italian: vowel groups ~= syllables. Diphthongs collapse to one group."""
    groups = re.findall(r"[aeiouàèéìòù]+", word.lower())
    return max(1, len(groups)) if word else 0


def _count_syllables_en(word: str) -> int:
    """English heuristic: count vowel groups, drop silent trailing 'e'."""
    w = word.lower()
    w = re.sub(r"[^a-z]", "", w)
    if not w:
        return 0
    groups = re.findall(r"[aeiouy]+", w)
    count = len(groups)
    if w.endswith("e") and count > 1 and not w.endswith(("le", "ee", "ye")):
        count -= 1
    return max(1, count)


def estimate_syllables(word: str, language: str = "en") -> int:
    if language == "it":
        return _count_syllables_it(word)
    return _count_syllables_en(word)


def _line_syllables(line: str, language: str) -> int:
    words = re.findall(r"[a-zA-Zàèéìòùç']+", line)
    return sum(estimate_syllables(w, language) for w in words)


def _ending_phonetic_hint(word: str) -> str:
    w = re.sub(r"[^a-zàèéìòù]", "", word.lower())
    if not w:
        return ""
    return w[-3:] if len(w) >= 3 else w


def _stress_hint(word: str, language: str) -> str:
    """Rough stress placement guess (penultimate default for IT)."""
    syl = estimate_syllables(word, language)
    if syl <= 1:
        return "monosyllable"
    if language == "it":
        if re.search(r"[àèéìòù]$", word.lower()):
            return "oxytone (final stress)"
        return "paroxytone (penultimate)"
    return "variable"


def analyze_lines_prosody(lyrics: str, language: str = "auto") -> dict[str, Any]:
    """Per-line prosody: syllables, endings, stress hints, rhyme candidates."""
    normalized = normalize_lyrics(lyrics)
    lang = detect_language(normalized) if language == "auto" else language

    raw_lines = [l for l in normalized.splitlines() if l.strip()]
    repeated = {item["line"] for item in find_repeated_lines(normalized)}

    lines: list[dict[str, Any]] = []
    syllable_counts: list[int] = []
    ending_map: dict[str, list[int]] = {}

    for idx, line in enumerate(raw_lines):
        words = re.findall(r"[a-zA-Zàèéìòùç']+", line)
        syl = _line_syllables(line, lang)
        syllable_counts.append(syl)
        ending_word = words[-1] if words else ""
        phon = _ending_phonetic_hint(ending_word)
        if phon:
            ending_map.setdefault(phon, []).append(idx)
        lines.append(
            {
                "line_index": idx,
                "text": line,
                "word_count": len(words),
                "estimated_syllables": syl,
                "ending_word": ending_word,
                "ending_phonetic_hint": phon,
                "stress_hint": _stress_hint(ending_word, lang) if ending_word else "",
                "is_repeated": line.strip().lower() in repeated,
            }
        )

    avg = round(sum(syllable_counts) / len(syllable_counts), 2) if syllable_counts else 0.0
    if syllable_counts:
        var = round(sum((c - avg) ** 2 for c in syllable_counts) / len(syllable_counts), 2)
    else:
        var = 0.0

    rhyme_candidates = [
        {"ending": ending, "line_indices": idxs}
        for ending, idxs in ending_map.items()
        if len(idxs) > 1
    ]

    warnings: list[str] = []
    if not raw_lines:
        warnings.append("No lyric lines to analyze.")
    if var > 25:
        warnings.append("High syllable variance across lines — verse meter is irregular.")

    return {
        "language": lang,
        "lines": lines,
        "average_syllables_per_line": avg,
        "syllable_variance": var,
        "rhyme_candidates": rhyme_candidates,
        "warnings": warnings,
    }
