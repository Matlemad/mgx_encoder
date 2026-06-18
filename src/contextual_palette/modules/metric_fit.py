"""Palette module: Metric Fit — compare lyric syllables vs melodic slots."""
from __future__ import annotations

import re
from typing import Any

from ..selection_analyzer import SelectionType

id = "metric_fit"
title = "Metric Fit"
supported_types = [SelectionType.PHRASE, SelectionType.STANZA, SelectionType.CHORUS]


def _estimate_syllables(text: str) -> int:
    words = re.findall(r"[a-zA-Zàèéìòù']+", text.lower())
    count = 0
    for w in words:
        groups = re.findall(r"[aeiouyàèéìòù]+", w)
        count += max(1, len(groups))
    return count


def _last_word(text: str) -> str:
    words = re.findall(r"[a-zA-Zàèéìòù']+", text)
    return words[-1] if words else ""


def run(text: str, context: dict[str, Any]) -> dict[str, Any]:
    estimated = _estimate_syllables(text)
    n_lines = max(1, len([l for l in text.splitlines() if l.strip()]))

    vocal_midi = context.get("vocal_midi") or {}
    rhythm = (context.get("mgx") or {}).get("R", {})
    bpm = rhythm.get("bpm") or context.get("bpm") or 0

    slots = 0
    source = "heuristic"
    mode = "heuristic"
    problems: list[str] = []
    has_midi = bool(vocal_midi and vocal_midi.get("suggested_syllable_slots"))

    if has_midi:
        phrases = vocal_midi.get("phrase_estimates", [])
        if phrases:
            # Use average phrase length scaled to the number of selected lines.
            avg_slots = sum(p["syllable_slots"] for p in phrases) / len(phrases)
            slots = int(round(avg_slots * n_lines))
        else:
            slots = int(vocal_midi["suggested_syllable_slots"])
        source = "vocal_midi"
        mode = "melody-aware"
    else:
        # Heuristic: at ~moderate tempo, a comfortable line holds ~6-10 syllables.
        per_line = 8
        if bpm:
            if bpm > 130:
                per_line = 6
            elif bpm < 80:
                per_line = 10
        slots = per_line * n_lines
        problems.append("No vocal MIDI: melodic slots estimated from BPM and line count (heuristic mode).")

    # Target syllable window (slightly tolerant around the slot count).
    target_min = max(1, slots - 1)
    target_max = slots + 1

    diff = estimated - slots
    if slots > 0:
        fit_score = round(max(0.0, 1.0 - abs(diff) / slots), 2)
    else:
        fit_score = 0.0

    slot_phrase = (f"the vocal melody phrase suggests {target_min}\u2013{target_max} syllable slots"
                   if mode == "melody-aware"
                   else f"a comfortable phrase here holds about {target_min}\u2013{target_max} syllables")

    if diff > 2:
        diagnosis = (f"This line has {estimated} estimated syllables, while {slot_phrase}. "
                     f"It will probably feel rushed.")
        problems.append("Words will likely rush against the melody.")
    elif diff < -2:
        diagnosis = (f"This line has {estimated} estimated syllables, while {slot_phrase}. "
                     f"The melody may have empty notes / feel stretched.")
        problems.append("Consider adding a word or extending an image.")
    else:
        diagnosis = (f"This line has {estimated} estimated syllables, and {slot_phrase}. "
                     f"It fits comfortably.")

    suggested = []
    if diff > 2:
        suggested.append(f"Cut ~{diff} syllables, e.g. drop a filler word or contract phrasing.")
    elif diff < -2:
        suggested.append(f"Add ~{abs(diff)} syllables with a concrete detail, keep the last word.")

    return {
        "module": "metric_fit",
        "mode": mode,
        "selected_text": text[:200],
        "estimated_syllables": estimated,
        "available_melodic_slots": slots,
        "slots_source": source,
        "fit_score": fit_score,
        "diagnosis": diagnosis,
        "problems": problems,
        "suggested_adjustments": suggested,
        "suggested_target_syllable_range": [target_min, target_max],
        "rewrite_targets": {
            "min_syllables": target_min,
            "max_syllables": target_max,
            "preserve_last_word": True,
            "preserve_rhyme": True,
        },
    }
