"""M — Melody analysis module.

Stable predominant-pitch extraction with aggressive smoothing,
semitone quantisation, voiced-frame tracking, and multi-pass agreement.
"""
from __future__ import annotations

from typing import Any

import librosa
import numpy as np
from scipy.ndimage import median_filter

from .preprocessing import PreprocessedAudio
from .multipass import run_on_passes, aggregate_numeric
from .utils import safe_float, safe_list


# ---------------------------------------------------------------------------
# Core pitch extraction
# ---------------------------------------------------------------------------

def _predominant_pitch(y: np.ndarray, sr: int) -> dict[str, Any]:
    """Extract predominant pitch with magnitude-weighted selection.

    Returns raw Hz track, voiced mask, and frame-level magnitudes.
    """
    pitches, magnitudes = librosa.piptrack(y=y, sr=sr, fmin=80, fmax=4000)
    n_frames = pitches.shape[1]

    raw_hz = np.zeros(n_frames)
    voiced = np.zeros(n_frames, dtype=bool)
    mags = np.zeros(n_frames)

    for t in range(n_frames):
        mag_col = magnitudes[:, t]
        if mag_col.max() == 0:
            continue
        # take top-3 bins by magnitude, pick the one with highest pitch
        top_k = min(3, int(np.sum(mag_col > 0)))
        if top_k == 0:
            continue
        top_idx = np.argsort(mag_col)[-top_k:]
        top_pitches = pitches[top_idx, t]
        top_mags = mag_col[top_idx]
        # weighted average among strong bins
        valid = top_pitches > 0
        if not np.any(valid):
            continue
        weighted_p = float(np.average(top_pitches[valid], weights=top_mags[valid]))
        raw_hz[t] = weighted_p
        voiced[t] = True
        mags[t] = float(np.max(top_mags[valid]))

    return {"raw_hz": raw_hz, "voiced": voiced, "magnitudes": mags}


# ---------------------------------------------------------------------------
# Smoothing & quantisation
# ---------------------------------------------------------------------------

def _smooth_pitch(raw_hz: np.ndarray, voiced: np.ndarray, sr: int) -> np.ndarray:
    """Multi-stage smoothing of the raw pitch track.

    1. Zero out unvoiced frames.
    2. Median filter (size=7) to kill transient noise.
    3. Linear-interp small gaps (<=3 frames).
    4. Second, wider median (size=11) for global stability.
    """
    smoothed = raw_hz.copy()
    smoothed[~voiced] = 0

    non_zero = smoothed > 0
    if np.sum(non_zero) < 5:
        return smoothed

    smoothed[non_zero] = median_filter(smoothed[non_zero], size=min(7, np.sum(non_zero)))

    # Interpolate short gaps
    idx = np.arange(len(smoothed))
    nz_mask = smoothed > 0
    if np.sum(nz_mask) >= 2:
        interp_vals = np.interp(idx, idx[nz_mask], smoothed[nz_mask])
        gap_lengths = np.zeros(len(smoothed), dtype=int)
        count = 0
        for i in range(len(smoothed)):
            if smoothed[i] == 0:
                count += 1
            else:
                count = 0
            gap_lengths[i] = count
        fill_mask = (smoothed == 0) & (gap_lengths <= 3) & (gap_lengths > 0)
        smoothed[fill_mask] = interp_vals[fill_mask]

    nz2 = smoothed > 0
    if np.sum(nz2) >= 11:
        smoothed[nz2] = median_filter(smoothed[nz2], size=min(11, np.sum(nz2)))

    return smoothed


def _quantise_to_semitones(hz_track: np.ndarray) -> np.ndarray:
    """Quantise Hz values to nearest MIDI semitone (as Hz).

    Sub-semitone wiggles are collapsed.  Unvoiced frames stay at 0.
    """
    out = np.zeros_like(hz_track)
    mask = hz_track > 20
    midi = librosa.hz_to_midi(hz_track[mask])
    midi_rounded = np.round(midi)
    out[mask] = librosa.midi_to_hz(midi_rounded)
    return out


# ---------------------------------------------------------------------------
# Interval & contour from quantised track
# ---------------------------------------------------------------------------

def _intervals_from_quantised(q_hz: np.ndarray) -> np.ndarray:
    """Semitone-interval sequence from quantised pitch (non-zero frames only)."""
    active = q_hz[q_hz > 20]
    if len(active) < 2:
        return np.array([])
    midi = librosa.hz_to_midi(active)
    intervals = np.diff(midi)
    intervals = np.round(intervals).astype(int)
    return intervals


def _contour_symbols(intervals: np.ndarray) -> list[str]:
    """Map interval sequence to contour symbols: U(p), D(own), R(epeat)."""
    symbols = []
    for iv in intervals:
        if iv > 0:
            symbols.append("U")
        elif iv < 0:
            symbols.append("D")
        else:
            symbols.append("R")
    return symbols


# ---------------------------------------------------------------------------
# Arrangement-invariant descriptors
# ---------------------------------------------------------------------------

def _interval_histogram(intervals: np.ndarray) -> list[float]:
    """Distribution of semitone intervals from -12 to +12 (25 bins).

    Transposition-invariant: identical melodies in different keys produce
    the same histogram.
    """
    bins = np.zeros(25)
    for iv in intervals:
        idx = int(np.clip(iv + 12, 0, 24))
        bins[idx] += 1
    total = bins.sum()
    if total > 0:
        bins = bins / total
    return bins.tolist()


def _contour_bigrams(symbols: list[str]) -> dict[str, float]:
    """Distribution of contour bigrams (UU, UD, UR, DU, DD, DR, RU, RD, RR).

    Captures melodic shape independent of absolute pitch and tempo.
    """
    all_bigrams = ["UU", "UD", "UR", "DU", "DD", "DR", "RU", "RD", "RR"]
    counts = {b: 0 for b in all_bigrams}
    for i in range(len(symbols) - 1):
        bg = symbols[i] + symbols[i + 1]
        if bg in counts:
            counts[bg] += 1
    total = sum(counts.values())
    if total > 0:
        counts = {k: round(v / total, 4) for k, v in counts.items()}
    return counts


def _pitch_class_profile_relative(pc_hist: np.ndarray, key_root_idx: int) -> list[float]:
    """Rotate pitch-class histogram so key center = index 0.

    Makes the profile key-invariant: the same melody in C major and E major
    produce the same relative distribution.
    """
    rotated = np.roll(pc_hist, -key_root_idx)
    total = rotated.sum()
    if total > 0:
        rotated = rotated / total
    return rotated.tolist()


def _pc_transition_matrix(q_hz: np.ndarray) -> list[list[float]]:
    """12x12 pitch-class transition matrix (row=from, col=to), normalized per row.

    Captures which notes follow which — invariant to tempo, rhythm, timbre.
    """
    active = q_hz[q_hz > 20]
    mat = np.zeros((12, 12))
    if len(active) < 2:
        return mat.tolist()
    midi = np.round(librosa.hz_to_midi(active)).astype(int)
    pcs = midi % 12
    for i in range(len(pcs) - 1):
        mat[pcs[i], pcs[i + 1]] += 1
    row_sums = mat.sum(axis=1, keepdims=True)
    mat = mat / (row_sums + 1e-8)
    return np.round(mat, 4).tolist()


# ---------------------------------------------------------------------------
# Per-signal extraction
# ---------------------------------------------------------------------------

def _extract_melody(y: np.ndarray, sr: int) -> dict[str, Any]:
    """Full melodic feature extraction for one signal pass."""
    pp_result = _predominant_pitch(y, sr)
    raw_hz = pp_result["raw_hz"]
    voiced = pp_result["voiced"]

    smoothed = _smooth_pitch(raw_hz, voiced, sr)
    quantised = _quantise_to_semitones(smoothed)

    voiced_ratio = float(np.mean(voiced))
    n_voiced = int(np.sum(voiced))

    # Stats from smoothed track (voiced frames only)
    active_smooth = smoothed[smoothed > 20]
    active_quant = quantised[quantised > 20]

    if len(active_smooth) > 1:
        pitch_range_hz = float(np.ptp(active_smooth))
        pitch_mean_hz = float(np.mean(active_smooth))
        pitch_std_hz = float(np.std(active_smooth))
    else:
        pitch_range_hz = 0.0
        pitch_mean_hz = float(np.mean(active_smooth)) if len(active_smooth) else 0.0
        pitch_std_hz = 0.0

    intervals = _intervals_from_quantised(quantised)

    if len(intervals) > 0:
        abs_intervals = np.abs(intervals)
        mean_interval = float(np.mean(abs_intervals))
        contour_direction = float(np.mean(np.sign(intervals)))
        stepwise = float(np.mean(abs_intervals <= 2))
    else:
        mean_interval = 0.0
        contour_direction = 0.0
        stepwise = 0.0

    contour = _contour_symbols(intervals)

    # Pitch-class histogram from quantised track (for melody/harmony agreement)
    pc_hist = np.zeros(12)
    if len(active_quant) > 0:
        midi_vals = librosa.hz_to_midi(active_quant)
        for m in midi_vals:
            pc_hist[int(round(m)) % 12] += 1
        pc_total = pc_hist.sum()
        if pc_total > 0:
            pc_hist = pc_hist / pc_total

    iv_hist = _interval_histogram(intervals)
    bigrams = _contour_bigrams(contour)
    pc_trans = _pc_transition_matrix(quantised)

    return {
        "pitch_range_hz": pitch_range_hz,
        "pitch_mean_hz": pitch_mean_hz,
        "pitch_std_hz": pitch_std_hz,
        "mean_interval_semitones": mean_interval,
        "contour_direction": contour_direction,
        "stepwise_ratio": stepwise,
        "voiced_ratio": voiced_ratio,
        "n_voiced_frames": n_voiced,
        "n_pitch_frames": len(raw_hz),
        "pitch_class_histogram": pc_hist.tolist(),
        "contour_symbols": contour[:200],
        "interval_histogram": iv_hist,
        "contour_bigrams": bigrams,
        "pc_transition_matrix": pc_trans,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_melody(pp: PreprocessedAudio) -> dict[str, Any]:
    """Full melody analysis with multi-pass + stability metrics."""
    passes = ["B_harmonic", "E_midhigh"]
    results = run_on_passes(pp, passes, _extract_melody)

    pitch_range = aggregate_numeric(results, "pitch_range_hz", weights=[0.6, 0.4])
    pitch_mean = aggregate_numeric(results, "pitch_mean_hz", weights=[0.6, 0.4])
    pitch_std = aggregate_numeric(results, "pitch_std_hz", weights=[0.6, 0.4])
    mean_interval = aggregate_numeric(results, "mean_interval_semitones", weights=[0.6, 0.4])
    contour_dir = aggregate_numeric(results, "contour_direction", weights=[0.6, 0.4])
    stepwise = aggregate_numeric(results, "stepwise_ratio", weights=[0.6, 0.4])
    voiced_ratio = aggregate_numeric(results, "voiced_ratio", weights=[0.6, 0.4])

    # Aggregate pitch-class histograms for melody/harmony agreement
    pc_hists = [np.array(r.get("pitch_class_histogram", [0]*12))
                for r in results if "pitch_class_histogram" in r]
    if pc_hists:
        agg_pc = np.mean(pc_hists, axis=0)
        agg_pc = agg_pc / (agg_pc.sum() + 1e-8)
    else:
        agg_pc = np.zeros(12)

    # Best contour symbols from harmonic pass
    contour_symbols = []
    for r in results:
        if r.get("contour_symbols") and r.get("_pass") == "B_harmonic":
            contour_symbols = r["contour_symbols"]
            break
    if not contour_symbols:
        for r in results:
            if r.get("contour_symbols"):
                contour_symbols = r["contour_symbols"]
                break

    # Aggregate interval histograms (already transposition-invariant)
    iv_hists = [np.array(r.get("interval_histogram", [0]*25))
                for r in results if "interval_histogram" in r]
    if iv_hists:
        agg_iv = np.mean(iv_hists, axis=0)
        total = agg_iv.sum()
        if total > 0:
            agg_iv = agg_iv / total
    else:
        agg_iv = np.zeros(25)

    # Aggregate contour bigrams
    all_bg_keys = ["UU", "UD", "UR", "DU", "DD", "DR", "RU", "RD", "RR"]
    bg_accum = {k: 0.0 for k in all_bg_keys}
    bg_count = 0
    for r in results:
        bg = r.get("contour_bigrams")
        if bg:
            for k in all_bg_keys:
                bg_accum[k] += bg.get(k, 0.0)
            bg_count += 1
    if bg_count > 0:
        bg_accum = {k: round(v / bg_count, 4) for k, v in bg_accum.items()}

    # Aggregate PC transition matrices
    pc_mats = [np.array(r.get("pc_transition_matrix", np.zeros((12, 12)).tolist()))
               for r in results if "pc_transition_matrix" in r]
    if pc_mats:
        agg_mat = np.mean(pc_mats, axis=0)
        row_sums = agg_mat.sum(axis=1, keepdims=True)
        agg_mat = agg_mat / (row_sums + 1e-8)
    else:
        agg_mat = np.zeros((12, 12))

    vocal_likelihood = _estimate_vocal_likelihood(pp)
    pitch_conf = _pitch_confidence(results)

    return {
        "pitch_range_hz": safe_float(pitch_range),
        "pitch_mean_hz": safe_float(pitch_mean),
        "pitch_std_hz": safe_float(pitch_std),
        "mean_interval_semitones": safe_float(mean_interval),
        "contour_direction": safe_float(contour_dir),
        "stepwise_ratio": safe_float(stepwise),
        "voiced_ratio": safe_float(voiced_ratio),
        "vocal_likelihood": safe_float(vocal_likelihood),
        "pitch_confidence": safe_float(pitch_conf),
        "pitch_class_histogram": agg_pc.tolist(),
        "contour_symbols": contour_symbols[:200],
        "interval_histogram": agg_iv.tolist(),
        "contour_bigrams": bg_accum,
        "pc_transition_matrix": np.round(agg_mat, 4).tolist(),
        "pass_details": results,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _estimate_vocal_likelihood(pp: PreprocessedAudio) -> float:
    """Heuristic: energy concentration in vocal range (200-4000 Hz)."""
    try:
        S = np.abs(librosa.stft(pp.y_mono))
        freqs = librosa.fft_frequencies(sr=pp.sr)
        vocal_mask = (freqs >= 200) & (freqs <= 4000)
        total_energy = np.sum(S**2) + 1e-8
        vocal_energy = np.sum(S[vocal_mask] ** 2)
        ratio = vocal_energy / total_energy
        return float(min(1.0, ratio * 1.5))
    except Exception:
        return 0.5


def _pitch_confidence(results: list[dict]) -> float:
    """Confidence from multi-pass agreement + voiced ratio."""
    means = [r.get("pitch_mean_hz", 0) for r in results if r.get("pitch_mean_hz", 0) > 0]
    voiced_ratios = [r.get("voiced_ratio", 0) for r in results if "voiced_ratio" in r]

    if len(means) < 2:
        base = 0.3
    else:
        spread = np.std(means) / (np.mean(means) + 1e-8)
        base = max(0.0, min(1.0, 1.0 - spread * 3))

    avg_voiced = float(np.mean(voiced_ratios)) if voiced_ratios else 0.3
    # Voiced ratio penalty: if too few voiced frames, pitch is unreliable
    voiced_factor = min(1.0, avg_voiced * 2.0)

    return float(max(0.0, min(1.0, base * 0.6 + voiced_factor * 0.4)))
