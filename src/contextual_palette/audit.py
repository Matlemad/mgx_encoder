"""Line/Block Audit — fast, deterministic analysis of a selected lyric.

Reuses the existing palette modules' logic and the full project context to
produce 0-100 scores plus a natural-language diagnosis. It NEVER calls an LLM
(rephrasing is a separate, on-demand step) and NEVER stores/echoes copyrighted
external text — references are abstract descriptors only.
"""
from __future__ import annotations

import re
from typing import Any

from .selection_analyzer import classify_selection
from .rephrase_selection import compute_line_targets
from .modules import (
    metric_fit,
    stress_alignment,
    singability_check,
    emotional_reading,
    cliche_detector,
    imagery_analyzer,
    rhyme_explorer,
)


def _safe_run(module: Any, text: str, context: dict[str, Any]) -> dict[str, Any]:
    try:
        return module.run(text, context) or {}
    except Exception:  # noqa: BLE001 - a single module must never break the audit
        return {}


def _rhyme_key(word: str) -> str:
    w = re.sub(r"[^a-zàèéìòùáéíóúñ]", "", word.lower())
    return w[-3:] if len(w) >= 3 else w


def _last_word(line: str) -> str:
    words = re.findall(r"[a-zA-Zàèéìòùáéíóúñ']+", line)
    return words[-1] if words else ""


def _rhyme_structure_score(selected_text: str, context: dict[str, Any]) -> tuple[int, str]:
    lines = [l for l in selected_text.splitlines() if l.strip()]
    if len(lines) >= 2:
        keys = [_rhyme_key(_last_word(l)) for l in lines]
        keys = [k for k in keys if k]
        if not keys:
            return 50, "No clear line endings to evaluate."
        rhymed = 0
        for i, k in enumerate(keys):
            if any(k and k == keys[j] for j in range(len(keys)) if j != i):
                rhymed += 1
        score = round(100 * rhymed / len(keys))
        if score >= 75:
            note = "Strong end-rhyme cohesion across the block."
        elif score >= 40:
            note = "Partial rhyme scheme — some lines rhyme, others are open."
        else:
            note = "Loose / slant endings — little end-rhyme cohesion."
        return score, note
    # Single line: judge rhymability of the final word.
    r = _safe_run(rhyme_explorer, selected_text, context)
    n = len(r.get("perfect_rhymes", [])) + len(r.get("near_rhymes", []))
    if n >= 4:
        return 70, "The final word has many rhyme partners (easy to close)."
    if n >= 1:
        return 60, "The final word has some rhyme options."
    return 45, "The final word is hard to rhyme — consider the closing word."


def _imagery_strength(selected_text: str, context: dict[str, Any]) -> tuple[int, list[str]]:
    senses = _safe_run(imagery_analyzer, selected_text, context)
    present = [s for s, v in senses.items() if isinstance(v, (int, float)) and v > 0]
    words = [w for w in re.findall(r"[a-zA-Zàèéìòù']+", selected_text.lower())]
    # Density of sensory hits relative to a typical short line.
    hit_density = len(present) / max(1, min(len(words), 8))
    score = round(min(100, 35 + 65 * hit_density)) if words else 0
    notes = []
    if present:
        notes.append("Senses present: " + ", ".join(present) + ".")
    else:
        notes.append("Mostly abstract — consider a concrete sensory image.")
    return score, notes


def _reference_alignment(selected_text: str, context: dict[str, Any]) -> tuple[int | None, dict[str, Any]]:
    ref = context.get("reference_profile") or {}
    patterns = ref.get("abstract_patterns", {}) if isinstance(ref, dict) else {}
    info: dict[str, Any] = {
        "source": ref.get("source") or "none",
        "active_artist": None,
        "related_themes": [],
        "alignment_notes": [],
    }
    if not patterns or not (ref.get("artists")):
        info["alignment_notes"].append("No reference profile set — add reference artists in the References tab.")
        return None, info

    vocab = set(re.findall(r"[a-zA-Zàèéìòù']+", selected_text.lower()))
    pool: list[str] = []
    for key in ("common_themes", "lexical_fields", "symbolic_register"):
        pool.extend([str(x).lower() for x in (patterns.get(key) or [])])
    pool = list(dict.fromkeys(pool))
    info["related_themes"] = (patterns.get("common_themes") or [])[:6]

    if not pool:
        return 55, info
    overlap = sum(1 for term in pool if any(tok in term or term in tok for tok in vocab if len(tok) > 2))
    score = round(min(100, 40 + 60 * (overlap / max(1, min(len(pool), 8)))))
    if overlap:
        info["alignment_notes"].append(f"Shares {overlap} territory term(s) with the reference direction.")
    else:
        info["alignment_notes"].append("No overlap yet with the reference themes — an opportunity to pull closer or stay distinct.")
    return score, info


def build_selection_audit(selected_text: str, context: dict[str, Any]) -> dict[str, Any]:
    """Produce a deterministic Line/Block audit for the selected lyric."""
    selected_text = (selected_text or "").strip()
    full_lyrics = context.get("full_lyrics", "") or ""

    sel_type = context.get("selection_type")
    if not sel_type:
        sel_type = classify_selection(selected_text, full_lyrics).value
    sel_type = str(sel_type).upper()

    if not selected_text:
        return {"selection_type": sel_type, "empty": True}

    mf = _safe_run(metric_fit, selected_text, context)
    sa = _safe_run(stress_alignment, selected_text, context)
    sc = _safe_run(singability_check, selected_text, context)
    er = _safe_run(emotional_reading, selected_text, context)
    cd = _safe_run(cliche_detector, selected_text, context)

    metric_fit_score = round((mf.get("fit_score") or 0) * 100)
    stress_score = round((sa.get("alignment_score") or 0) * 100)
    singability_score = int(sc.get("singability_score") or 0)
    mood_score = round((er.get("alignment_score") or 0) * 100)
    cliche_risk = int(cd.get("cliche_score") or 0)
    rhyme_score, rhyme_note = _rhyme_structure_score(selected_text, context)
    imagery_score, imagery_notes = _imagery_strength(selected_text, context)
    ref_score, ref_info = _reference_alignment(selected_text, context)

    # Per-line syllable targets, mapped to the corresponding vocal-MIDI phrases.
    _rng = mf.get("suggested_target_syllable_range")
    _nlines = len([l for l in selected_text.splitlines() if l.strip()]) or 1
    _fb = (max(2, round(((_rng[0] + _rng[1]) / 2) / _nlines))
           if (_rng and len(_rng) == 2) else None)
    per_line_targets = compute_line_targets(selected_text, context, fallback_per_line=_fb)

    scores = {
        "metric_fit": metric_fit_score,
        "stress_alignment": stress_score,
        "singability": singability_score,
        "mood_alignment": mood_score,
        "rhyme_structure": rhyme_score,
        "cliche_risk": cliche_risk,
        "imagery_strength": imagery_score,
        "reference_alignment": ref_score if ref_score is not None else 0,
    }

    # ── diagnosis ──
    what_works: list[str] = []
    what_does_not: list[str] = []
    actions: list[str] = []

    if metric_fit_score >= 70:
        what_works.append(f"Fits the melodic phrase well (metric fit {metric_fit_score}/100).")
    elif metric_fit_score < 55:
        what_does_not.append(f"Syllable count is off for the melody (metric fit {metric_fit_score}/100).")
    for p in (mf.get("suggested_adjustments") or []):
        actions.append(p)

    if stress_score >= 70:
        what_works.append("Key words mostly land on strong positions.")
    elif stress_score < 55:
        what_does_not.append("Important words sit in weak metric spots.")
        actions.extend(sa.get("suggestions", [])[:1])

    if singability_score >= 70:
        what_works.append("Comfortable to sing.")
    elif singability_score < 60:
        what_does_not.append("May be hard to articulate (consonant clusters / low vowel ratio).")
        actions.extend(sc.get("suggestions", [])[:1])

    if mood_score >= 70:
        what_works.append(f"Tone matches the music ({er.get('lyrics_emotion')} ~ {er.get('music_emotion')}).")
    elif mood_score < 55:
        what_does_not.append(f"Lyric mood ({er.get('lyrics_emotion')}) diverges from music ({er.get('music_emotion')}).")

    if cliche_risk >= 60:
        what_does_not.append(f"Cliché risk is high ({cliche_risk}/100).")
        if cd.get("alternatives"):
            actions.append("Replace the cliché, e.g. " + ", ".join(cd["alternatives"][:3]) + ".")

    if imagery_score >= 70:
        what_works.append("Strong concrete imagery.")
    elif imagery_score < 50:
        what_does_not.append("Imagery is thin / abstract.")
        actions.append("Add one concrete sensory detail the listener can picture.")

    if ref_score is not None and ref_score >= 70:
        what_works.append("Aligned with the chosen reference direction.")

    if not actions:
        actions.append("Solid line — small polish only; try sharpening the strongest image.")

    # ── summary blurb ──
    labels = {
        "metric_fit": "metric fit", "stress_alignment": "stress placement",
        "singability": "singability", "mood_alignment": "mood match",
        "rhyme_structure": "rhyme", "imagery_strength": "imagery",
        "reference_alignment": "reference fit",
    }
    positive = {k: v for k, v in scores.items() if k in labels}
    best = max(positive, key=positive.get)
    worst = min(positive, key=positive.get)
    if scores[best] - scores[worst] < 10:
        blurb = "A balanced line — no single dimension stands out; refine to taste."
    else:
        blurb = (f"Strongest in {labels[best]} ({scores[best]}/100); weakest in "
                 f"{labels[worst]} ({scores[worst]}/100)"
                 + (f", and cliché risk is {cliche_risk}/100." if cliche_risk >= 60 else "."))

    return {
        "selection_type": sel_type,
        "summary_blurb": blurb,
        "scores": scores,
        "diagnosis": {
            "what_works": what_works,
            "what_does_not_work": what_does_not,
            "recommended_action": list(dict.fromkeys(actions)),
        },
        "metric": {
            "mode": mf.get("mode", "heuristic"),
            "estimated_syllables": mf.get("estimated_syllables"),
            "target_syllable_range": mf.get("suggested_target_syllable_range"),
            "available_melodic_slots": mf.get("available_melodic_slots"),
            "per_line_targets": per_line_targets,
            "problems": mf.get("problems", []),
            "rewrite_targets": mf.get("rewrite_targets", {}),
        },
        "reference": {
            "source": ref_info["source"],
            "active_artist": ref_info["active_artist"],
            "related_themes": ref_info["related_themes"],
            "alignment_notes": ref_info["alignment_notes"],
            "score": ref_score,
        },
        "rhyme_note": rhyme_note,
        "imagery_notes": imagery_notes,
        "safety_note": "No copyrighted lyrics or external text used — abstract descriptors only.",
    }
