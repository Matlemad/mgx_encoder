"""H — Harmony analysis module.

Multi-chroma key detection with candidate ranking, mode ambiguity handling,
section-weighted tonal profiles, and tiered chord estimation.
"""
from __future__ import annotations

from typing import Any

import librosa
import numpy as np

from .preprocessing import PreprocessedAudio
from .utils import safe_float

_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Krumhansl-Kessler profiles
_MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# Temperley profiles (often better for pop/rock)
_MAJOR_TEMPERLEY = np.array([5.0, 2.0, 3.5, 2.0, 4.5, 4.0, 2.0, 4.5, 2.0, 3.5, 1.5, 4.0])
_MINOR_TEMPERLEY = np.array([5.0, 2.0, 3.5, 4.5, 2.0, 3.5, 2.0, 4.5, 3.5, 2.0, 1.5, 4.0])


# ---------------------------------------------------------------------------
# Key estimation core
# ---------------------------------------------------------------------------

def _correlate_all_keys(chroma_profile: np.ndarray) -> list[dict[str, Any]]:
    """Correlate a 12-dim chroma profile with all 24 major/minor keys.

    Uses both Krumhansl-Kessler and Temperley templates, takes the best
    correlation per key as the score.  Returns sorted list (best first).
    """
    candidates: list[dict[str, Any]] = []
    for shift in range(12):
        rolled = np.roll(chroma_profile, -shift)

        c_maj_kk = float(np.corrcoef(rolled, _MAJOR_PROFILE)[0, 1])
        c_min_kk = float(np.corrcoef(rolled, _MINOR_PROFILE)[0, 1])
        c_maj_t = float(np.corrcoef(rolled, _MAJOR_TEMPERLEY)[0, 1])
        c_min_t = float(np.corrcoef(rolled, _MINOR_TEMPERLEY)[0, 1])

        score_maj = max(c_maj_kk, c_maj_t)
        score_min = max(c_min_kk, c_min_t)

        candidates.append({"key": _NOTE_NAMES[shift], "mode": "major", "score": score_maj})
        candidates.append({"key": _NOTE_NAMES[shift], "mode": "minor", "score": score_min})

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates


def _key_from_chroma(chroma_2d: np.ndarray) -> dict[str, Any]:
    """Estimate key from a 2-D chroma matrix (12 x T).

    Returns dict with best key/mode/score and full ranked candidates.
    """
    if chroma_2d.size == 0:
        return {"key": "C", "mode": "major", "score": 0.0, "candidates": []}

    profile = np.mean(chroma_2d, axis=1)
    profile = profile / (profile.max() + 1e-8)
    candidates = _correlate_all_keys(profile)
    best = candidates[0]
    return {
        "key": best["key"],
        "mode": best["mode"],
        "score": best["score"],
        "candidates": candidates[:6],
        "profile": profile.tolist(),
    }


# ---------------------------------------------------------------------------
# Multi-chroma voting
# ---------------------------------------------------------------------------

def _multi_chroma_key_vote(pp: PreprocessedAudio) -> dict[str, Any]:
    """Run key detection on multiple chroma representations and vote.

    Weights:
      chroma_cqt_harmonic  0.35  (best for tonal centre from harmonic signal)
      chroma_cens_harmonic 0.30  (smoothed, robust to noise)
      chroma_cqt           0.15  (full mix CQT)
      chroma_cens          0.10  (full mix CENS)
      chroma_stft          0.10  (supplementary)
    """
    sources = {
        "cqt_harmonic": (pp.chroma_cqt_harmonic, 0.35),
        "cens_harmonic": (pp.chroma_cens_harmonic, 0.30),
        "cqt_full": (pp.chroma_cqt, 0.15),
        "cens_full": (pp.chroma_cens, 0.10),
        "stft_full": (pp.chroma_stft, 0.10),
    }

    per_source: list[dict[str, Any]] = []
    weighted_scores: dict[str, float] = {}

    for name, (chroma, weight) in sources.items():
        if chroma.size == 0:
            continue
        result = _key_from_chroma(chroma)
        result["_source"] = name
        result["_weight"] = weight
        per_source.append(result)

        for cand in result["candidates"]:
            label = f"{cand['key']}_{cand['mode']}"
            weighted_scores[label] = weighted_scores.get(label, 0.0) + cand["score"] * weight

    if not weighted_scores:
        return {
            "key_center": "C", "key_mode": "major", "key_confidence": 0.0,
            "key_candidates": [], "mode_ambiguity": "unknown",
            "per_source": per_source,
        }

    ranked = sorted(weighted_scores.items(), key=lambda x: x[1], reverse=True)

    best_label = ranked[0][0]
    best_score = ranked[0][1]
    best_key, best_mode = best_label.rsplit("_", 1)

    top3 = []
    for label, score in ranked[:3]:
        k, m = label.rsplit("_", 1)
        top3.append({"key": k, "mode": m, "score": round(score, 4)})

    # --- confidence from gap between top candidates ---
    # Distinguish root-change vs mode-only-change in the runner-up.
    if len(ranked) >= 2:
        runner_label = ranked[1][0]
        runner_key, runner_mode = runner_label.rsplit("_", 1)
        gap = best_score - ranked[1][1]
        closeness = gap / (best_score + 1e-8)

        if runner_key == best_key:
            # Same root, different mode — tonal center is stable.
            # Give higher confidence since root identification is solid.
            key_confidence = min(1.0, 0.50 + closeness * 3.0)
        else:
            key_confidence = min(1.0, closeness * 4.0)
    else:
        key_confidence = 0.5

    # --- mode ambiguity ---
    same_root_other_mode = f"{best_key}_{'minor' if best_mode == 'major' else 'major'}"
    other_mode_score = weighted_scores.get(same_root_other_mode, 0.0)
    mode_gap = abs(best_score - other_mode_score)
    if mode_gap < 0.05:
        mode_ambiguity = "high"
    elif mode_gap < 0.15:
        mode_ambiguity = "moderate"
    else:
        mode_ambiguity = "low"

    # relative major/minor ambiguity (e.g. E major vs C# minor)
    relative_key_idx = (_NOTE_NAMES.index(best_key) - 3) % 12 if best_mode == "major" else (_NOTE_NAMES.index(best_key) + 3) % 12
    relative_mode = "minor" if best_mode == "major" else "major"
    relative_label = f"{_NOTE_NAMES[relative_key_idx]}_{relative_mode}"
    relative_score = weighted_scores.get(relative_label, 0.0)
    relative_gap = abs(best_score - relative_score)

    notes: list[str] = []
    if mode_ambiguity in ("high", "moderate"):
        notes.append(f"Major/minor ambiguity for root {best_key} (gap={mode_gap:.3f})")
    if relative_gap < 0.10:
        rel_name = f"{_NOTE_NAMES[relative_key_idx]} {relative_mode}"
        notes.append(f"Relative key {rel_name} is close (gap={relative_gap:.3f})")

    return {
        "key_center": best_key,
        "key_mode": best_mode,
        "key_confidence": round(key_confidence, 4),
        "key_candidates": top3,
        "mode_ambiguity": mode_ambiguity,
        "per_source": per_source,
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# Section-weighted tonal profile
# ---------------------------------------------------------------------------

def _section_weighted_key(pp: PreprocessedAudio) -> dict[str, Any] | None:
    """Estimate key using section-level energy weighting.

    Downweights low-energy and percussive-heavy frames so intros, fills,
    and breakdowns don't pull the key estimate off centre.
    """
    chroma = pp.chroma_cqt_harmonic
    if chroma.size == 0:
        return None

    n_frames = chroma.shape[1]
    if n_frames < 10:
        return None

    hop_length = 512
    frame_energy = np.sum(chroma, axis=0)

    perc_rms = np.zeros(n_frames)
    try:
        perc_spec = np.abs(librosa.stft(pp.y_percussive))
        perc_energy = np.sum(perc_spec**2, axis=0)
        if len(perc_energy) >= n_frames:
            perc_rms = perc_energy[:n_frames]
        else:
            perc_rms[:len(perc_energy)] = perc_energy
    except Exception:
        pass

    weights = frame_energy / (frame_energy.max() + 1e-8)
    perc_norm = perc_rms / (perc_rms.max() + 1e-8)
    weights = weights * (1.0 - 0.5 * perc_norm)
    weights = np.clip(weights, 0.05, 1.0)

    weighted_profile = np.average(chroma, axis=1, weights=weights)
    weighted_profile = weighted_profile / (weighted_profile.max() + 1e-8)

    candidates = _correlate_all_keys(weighted_profile)
    best = candidates[0]
    return {
        "key": best["key"],
        "mode": best["mode"],
        "score": best["score"],
        "method": "section_weighted",
    }


# ---------------------------------------------------------------------------
# Chord estimation (tiered fallback)
# ---------------------------------------------------------------------------

_CHORD_TEMPLATES = {
    "maj": np.array([1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0], dtype=float),
    "min": np.array([1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0], dtype=float),
    "7":   np.array([1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 1, 0], dtype=float),
    "m7":  np.array([1, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0], dtype=float),
    "dim": np.array([1, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0, 0], dtype=float),
    "5":   np.array([1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0], dtype=float),
}


def _estimate_chords(chroma: np.ndarray, sr: int) -> dict[str, Any]:
    """Tiered chord estimation from chroma.

    Tier 1: full chord labels (if confident)
    Tier 2: root-only sequence (if chords are ambiguous)
    Tier 3: pitch-class emphasis only (if everything is weak)
    """
    if chroma.size == 0:
        return {"tier": 3, "chord_sequence": [], "root_sequence": [],
                "harmonic_emphasis": [0.0] * 12, "chord_confidence": 0.0}

    hop_sec = 512 / 22050
    beat_frames = max(1, int(0.5 / hop_sec))
    n_frames = chroma.shape[1]

    chord_seq: list[dict[str, Any]] = []
    root_seq: list[str] = []
    confidence_vals: list[float] = []

    for start in range(0, n_frames, beat_frames):
        end = min(start + beat_frames, n_frames)
        frame = np.mean(chroma[:, start:end], axis=1)
        frame_norm = frame / (frame.max() + 1e-8)

        best_chord = ""
        best_root = ""
        best_score = -1.0

        for root_idx in range(12):
            for label, template in _CHORD_TEMPLATES.items():
                rolled = np.roll(template, root_idx)
                score = float(np.dot(frame_norm, rolled) / (np.linalg.norm(frame_norm) * np.linalg.norm(rolled) + 1e-8))
                if score > best_score:
                    best_score = score
                    best_root = _NOTE_NAMES[root_idx]
                    best_chord = f"{best_root}{label}" if label != "maj" else best_root

        chord_seq.append({"chord": best_chord, "root": best_root, "score": round(best_score, 3)})
        root_seq.append(best_root)
        confidence_vals.append(best_score)

    mean_conf = float(np.mean(confidence_vals)) if confidence_vals else 0.0

    # Deduplicate consecutive identical chords
    deduped: list[dict[str, Any]] = []
    for c in chord_seq:
        if not deduped or deduped[-1]["chord"] != c["chord"]:
            deduped.append(c)

    deduped_roots: list[str] = []
    for r in root_seq:
        if not deduped_roots or deduped_roots[-1] != r:
            deduped_roots.append(r)

    # Tier selection
    if mean_conf >= 0.75:
        tier = 1
    elif mean_conf >= 0.55:
        tier = 2
    else:
        tier = 3

    harmonic_emphasis = np.mean(chroma, axis=1)
    harmonic_emphasis = (harmonic_emphasis / (harmonic_emphasis.max() + 1e-8)).tolist()

    max_chords = 64
    return {
        "tier": tier,
        "chord_sequence": [c["chord"] for c in deduped[:max_chords]] if tier == 1 else [],
        "root_sequence": deduped_roots[:max_chords] if tier <= 2 else [],
        "harmonic_emphasis": harmonic_emphasis,
        "chord_confidence": round(mean_conf, 4),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_harmony(pp: PreprocessedAudio) -> dict[str, Any]:
    """Full harmony analysis: multi-chroma key voting + chord estimation."""
    vote = _multi_chroma_key_vote(pp)
    section = _section_weighted_key(pp)

    # If section-weighted analysis agrees with voting, boost confidence
    section_agrees = False
    if section:
        if section["key"] == vote["key_center"] and section["mode"] == vote["key_mode"]:
            section_agrees = True

    final_confidence = vote["key_confidence"]
    if section_agrees:
        final_confidence = min(1.0, final_confidence + 0.15)
    elif section and section["key"] != vote["key_center"]:
        final_confidence = max(0.0, final_confidence - 0.1)
        vote.setdefault("notes", []).append(
            f"Section-weighted key ({section['key']} {section['mode']}) "
            f"disagrees with multi-chroma vote ({vote['key_center']} {vote['key_mode']})"
        )

    # Chord estimation on harmonic chroma
    chords = _estimate_chords(pp.chroma_cqt_harmonic, pp.sr)

    # Chroma entropy
    chroma = pp.chroma_cqt_harmonic
    if chroma.size > 0:
        chroma_entropy = float(np.mean(_entropy_per_frame(chroma)))
    else:
        chroma_entropy = 0.0

    # Harmonic change rate
    if chroma.size > 0:
        harmonic_change_rate = float(np.mean(np.abs(np.diff(chroma, axis=1))))
    else:
        harmonic_change_rate = 0.0

    # Tonnetz
    try:
        tonnetz = librosa.feature.tonnetz(y=pp.y_harmonic, sr=pp.sr)
        tonnetz_centroid = np.mean(tonnetz, axis=1).tolist()
    except Exception:
        tonnetz_centroid = [0.0] * 6

    # Aggregate chroma profile (energy-normalised, from best source)
    best_profile = vote["per_source"][0].get("profile", [0.0] * 12) if vote.get("per_source") else [0.0] * 12

    notes = vote.get("notes", [])

    # --- Arrangement-invariant features ---

    # Chroma profile rotated so key center = index 0
    key_root_idx = _NOTE_NAMES.index(vote["key_center"]) if vote["key_center"] in _NOTE_NAMES else 0
    chroma_relative = np.roll(np.array(best_profile), -key_root_idx)
    chroma_rel_sum = chroma_relative.sum()
    if chroma_rel_sum > 0:
        chroma_relative = chroma_relative / chroma_rel_sum

    # Relative root functions (scale degrees instead of absolute note names)
    _DEGREE_NAMES = ["I", "bII", "II", "bIII", "III", "IV", "bV", "V", "bVI", "VI", "bVII", "VII"]
    rel_root_funcs = []
    for root_name in chords.get("root_sequence", []):
        if root_name in _NOTE_NAMES:
            degree = (_NOTE_NAMES.index(root_name) - key_root_idx) % 12
            rel_root_funcs.append(_DEGREE_NAMES[degree])
        else:
            rel_root_funcs.append("?")

    rel_chord_funcs = []
    for chord_name in chords.get("chord_sequence", []):
        if not chord_name:
            continue
        root_part = chord_name[0]
        quality = ""
        if len(chord_name) > 1 and chord_name[1] == "#":
            root_part = chord_name[:2]
            quality = chord_name[2:]
        elif len(chord_name) > 1 and chord_name[1] not in "ABCDEFG#":
            quality = chord_name[1:]
        if root_part in _NOTE_NAMES:
            degree = (_NOTE_NAMES.index(root_part) - key_root_idx) % 12
            rel_chord_funcs.append(f"{_DEGREE_NAMES[degree]}{quality}")
        else:
            rel_chord_funcs.append(chord_name)

    # Harmonic emphasis rotated to key center
    harm_emp = np.array(chords.get("harmonic_emphasis", [0.0] * 12))
    harm_emp_relative = np.roll(harm_emp, -key_root_idx)
    he_sum = harm_emp_relative.sum()
    if he_sum > 0:
        harm_emp_relative = harm_emp_relative / he_sum

    # Harmonic rhythm: chord changes per beat (tempo-invariant)
    n_root_changes = max(0, len(chords.get("root_sequence", [])) - 1)
    bpm_est = 120.0
    try:
        import librosa as _lr
        _tempo = _lr.beat.beat_track(y=pp.y_mono, sr=pp.sr)[0]
        bpm_est = float(np.atleast_1d(_tempo)[0])
        if bpm_est < 30:
            bpm_est = 120.0
    except Exception:
        pass
    beats_total = (pp.duration_sec / 60.0) * bpm_est
    harm_rhythm_per_beat = n_root_changes / (beats_total + 1e-8)

    # backward-compatible key/mode fields
    return {
        "key": vote["key_center"],
        "mode": vote["key_mode"],
        "key_center": vote["key_center"],
        "key_mode": vote["key_mode"],
        "key_confidence": safe_float(final_confidence),
        "key_candidates": vote["key_candidates"],
        "mode_ambiguity": vote["mode_ambiguity"],
        "mode_confidence": safe_float(final_confidence),
        "tuning_offset_cents": safe_float(pp.tuning_offset_cents),
        "chroma_profile": best_profile,
        "harmonic_change_rate": safe_float(harmonic_change_rate),
        "chroma_entropy": safe_float(chroma_entropy),
        "tonnetz_centroid": tonnetz_centroid,
        "chord_tier": chords["tier"],
        "chord_sequence": chords["chord_sequence"],
        "root_sequence": chords["root_sequence"],
        "harmonic_emphasis": chords["harmonic_emphasis"],
        "chord_confidence": safe_float(chords["chord_confidence"]),
        "section_weighted_key": section,
        "chroma_profile_relative": chroma_relative.tolist(),
        "harmonic_emphasis_relative": harm_emp_relative.tolist(),
        "relative_root_functions": rel_root_funcs[:64],
        "relative_chord_functions": rel_chord_funcs[:64],
        "harmonic_rhythm_per_beat": safe_float(harm_rhythm_per_beat),
        "notes": notes,
        "pass_details": vote.get("per_source", []),
    }


def _entropy_per_frame(chroma: np.ndarray) -> np.ndarray:
    """Compute entropy of each chroma frame."""
    chroma_norm = chroma / (chroma.sum(axis=0, keepdims=True) + 1e-8)
    ent = -np.sum(chroma_norm * np.log2(chroma_norm + 1e-10), axis=0)
    return ent
