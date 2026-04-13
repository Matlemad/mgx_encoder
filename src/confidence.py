"""C — Confidence / meta-quality module.

Improved: factors in key-candidate closeness, melody/harmony agreement,
mode ambiguity, and voiced-pitch stability.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from .utils import safe_float

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _melody_harmony_agreement(melody: dict[str, Any], harmony: dict[str, Any]) -> tuple[float, list[str]]:
    """Check if dominant melody pitch classes align with the estimated key.

    Returns (agreement_score 0-1, list of notes).
    """
    notes: list[str] = []
    pc_hist = melody.get("pitch_class_histogram")
    key_center = harmony.get("key_center") or harmony.get("key", "C")
    key_mode = harmony.get("key_mode") or harmony.get("mode", "major")

    if pc_hist is None or not isinstance(pc_hist, list) or len(pc_hist) != 12:
        return 0.5, ["No pitch-class histogram available for agreement check"]

    pc_hist = np.array(pc_hist, dtype=float)
    if pc_hist.sum() < 1e-8:
        return 0.5, ["Melody pitch-class histogram is empty"]

    root_idx = _NOTE_NAMES.index(key_center) if key_center in _NOTE_NAMES else 0

    if key_mode == "major":
        scale_degrees = [0, 2, 4, 5, 7, 9, 11]
    else:
        scale_degrees = [0, 2, 3, 5, 7, 8, 10]

    in_key_mask = np.zeros(12)
    for d in scale_degrees:
        in_key_mask[(root_idx + d) % 12] = 1.0

    in_key_energy = float(np.sum(pc_hist * in_key_mask))
    total_energy = float(np.sum(pc_hist))
    agreement = in_key_energy / (total_energy + 1e-8)

    # Top melody pitch class
    top_pc = int(np.argmax(pc_hist))
    top_pc_name = _NOTE_NAMES[top_pc]

    if agreement < 0.5:
        notes.append(
            f"Melody pitch classes poorly aligned with {key_center} {key_mode} "
            f"(agreement={agreement:.2f}, dominant PC={top_pc_name})"
        )
    elif agreement < 0.7:
        notes.append(
            f"Moderate melody/harmony alignment (agreement={agreement:.2f})"
        )

    return agreement, notes


def compute_confidence(
    meta: dict[str, Any],
    rhythm: dict[str, Any],
    melody: dict[str, Any],
    harmony: dict[str, Any],
    motif: dict[str, Any],
    form: dict[str, Any],
) -> dict[str, Any]:
    """Aggregate confidence scores with improved tonal checks."""

    # --- Base field scores ---
    rhythm_conf = safe_float(rhythm.get("bpm_confidence", 0))
    melody_conf = safe_float(melody.get("pitch_confidence", 0))
    motif_conf = safe_float(motif.get("motif_confidence", 0))
    form_conf = safe_float(form.get("form_confidence", 0))

    # --- Harmony confidence (multi-factor) ---
    key_conf = safe_float(harmony.get("key_confidence", 0))

    # Penalise when key candidates are too close, but distinguish
    # root-ambiguity (bad) from mode-only ambiguity (less bad).
    candidates = harmony.get("key_candidates", [])
    if len(candidates) >= 2:
        c0, c1 = candidates[0], candidates[1]
        gap = c0.get("score", 0) - c1.get("score", 0)
        same_root = c0.get("key") == c1.get("key")
        if gap < 0.02 and not same_root:
            key_conf = min(key_conf, 0.25)
        elif gap < 0.02 and same_root:
            # Same root, different mode — tonal center is stable, only mode is uncertain
            key_conf = min(key_conf, max(key_conf, 0.45))

    # Mode ambiguity: penalise lightly (root center may still be solid)
    mode_amb = harmony.get("mode_ambiguity", "low")
    if mode_amb == "high":
        key_conf = max(0.0, key_conf - 0.08)
    elif mode_amb == "moderate":
        key_conf = max(0.0, key_conf - 0.03)

    # Melody/harmony agreement check
    mh_agreement, mh_notes = _melody_harmony_agreement(melody, harmony)
    if mh_agreement < 0.5:
        key_conf = max(0.0, key_conf - 0.15)
        melody_conf = max(0.0, melody_conf - 0.1)
    elif mh_agreement < 0.7:
        key_conf = max(0.0, key_conf - 0.05)

    harmony_conf = key_conf

    scores = {
        "rhythm": rhythm_conf,
        "melody": melody_conf,
        "harmony": harmony_conf,
        "motif": motif_conf,
        "form": form_conf,
    }

    overall = sum(scores.values()) / len(scores) if scores else 0.0

    # --- Warnings ---
    warnings: list[str] = []
    duration = meta.get("duration_sec", 0)
    if duration < 15:
        warnings.append("Audio very short (<15s) — results unreliable")
    elif duration < 30:
        warnings.append("Audio short (<30s) — some features may be imprecise")
    if duration > 600:
        warnings.append("Audio very long (>10min) — analysis may be slow")

    for field, score in scores.items():
        if score < 0.3:
            warnings.append(f"Low confidence in {field} ({score:.2f})")

    # Tuning warning
    tuning = harmony.get("tuning_offset_cents", 0)
    if abs(tuning) > 15:
        warnings.append(f"Significant detuning detected ({tuning:+.1f} cents) — tonal analysis compensated")

    # Key ambiguity warning
    if mode_amb in ("high", "moderate"):
        key_str = harmony.get("key_center", harmony.get("key", "?"))
        warnings.append(f"Major/minor mode ambiguity is {mode_amb} for root {key_str}")

    if mh_agreement < 0.5:
        warnings.append("Melody and harmony analysis show weak agreement")

    # --- Notes ---
    notes: list[str] = []
    notes.extend(mh_notes)
    notes.extend(harmony.get("notes", []))
    notes.extend(motif.get("notes", []))
    notes.extend(form.get("notes", []))

    return {
        "field_confidence": scores,
        "overall_confidence": safe_float(overall),
        "melody_harmony_agreement": safe_float(mh_agreement),
        "warnings": warnings,
        "notes": notes,
        "disclaimer": (
            "This output is a structural similarity aid derived from final "
            "mixed audio only. It is not a legal proof of plagiarism or authorship."
        ),
    }
