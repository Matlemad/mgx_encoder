"""R — Rhythm analysis module."""
from __future__ import annotations

from typing import Any

import librosa
import numpy as np

from .preprocessing import PreprocessedAudio
from .multipass import run_on_passes, aggregate_numeric
from .utils import safe_float, safe_list


def _extract_rhythm(y: np.ndarray, sr: int) -> dict[str, Any]:
    """Extract rhythm features from a single signal."""
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    tempo = float(np.atleast_1d(tempo)[0])

    beat_times = librosa.frames_to_time(beats, sr=sr)
    if len(beat_times) > 1:
        ibis = np.diff(beat_times)
        beat_regularity = 1.0 - float(np.std(ibis) / (np.mean(ibis) + 1e-8))
        beat_regularity = max(0.0, min(1.0, beat_regularity))
    else:
        ibis = np.array([])
        beat_regularity = 0.0

    onset_env = librosa.onset.onset_strength(y=y, sr=sr)

    tempogram = librosa.feature.tempogram(onset_envelope=onset_env, sr=sr)
    tempo_mean = float(np.mean(tempogram))

    ac = librosa.autocorrelate(onset_env, max_size=sr // 512 * 4)
    if len(ac) > 1:
        ac_norm = ac / (ac[0] + 1e-8)
        groove_complexity = 1.0 - float(np.max(ac_norm[1:min(len(ac_norm), 50)]))
        groove_complexity = max(0.0, min(1.0, groove_complexity))
    else:
        groove_complexity = 0.5

    swing = _estimate_swing(onset_env, sr)

    return {
        "bpm": tempo,
        "beat_regularity": beat_regularity,
        "groove_complexity": groove_complexity,
        "swing_ratio": swing,
        "onset_density": float(np.mean(onset_env)),
        "n_beats": int(len(beats)),
    }


def _estimate_swing(onset_env: np.ndarray, sr: int) -> float:
    """Rough swing estimation from onset autocorrelation."""
    if len(onset_env) < 20:
        return 0.5
    ac = librosa.autocorrelate(onset_env, max_size=len(onset_env) // 2)
    if len(ac) < 4:
        return 0.5
    ac = ac / (ac[0] + 1e-8)
    half = len(ac) // 2
    peak_idx = np.argmax(ac[1:half]) + 1
    if peak_idx < 2:
        return 0.5
    sub_peak = np.argmax(ac[1:peak_idx]) + 1
    ratio = sub_peak / (peak_idx + 1e-8)
    swing = max(0.3, min(0.7, ratio))
    return float(swing)


def analyze_rhythm(pp: PreprocessedAudio) -> dict[str, Any]:
    """Full rhythm analysis with multi-pass."""
    passes = ["A_mono", "C_percussive", "F_onset"]
    results = run_on_passes(pp, passes, _extract_rhythm)

    bpm = aggregate_numeric(results, "bpm", weights=[0.3, 0.5, 0.2])
    regularity = aggregate_numeric(results, "beat_regularity", weights=[0.3, 0.5, 0.2])
    complexity = aggregate_numeric(results, "groove_complexity", weights=[0.2, 0.5, 0.3])
    swing = aggregate_numeric(results, "swing_ratio", weights=[0.3, 0.4, 0.3])
    density = aggregate_numeric(results, "onset_density", weights=[0.3, 0.4, 0.3])

    time_sig = _guess_time_signature(pp)

    return {
        "bpm": safe_float(bpm),
        "bpm_confidence": _bpm_confidence(results),
        "time_signature": time_sig,
        "beat_regularity": safe_float(regularity),
        "groove_complexity": safe_float(complexity),
        "swing_ratio": safe_float(swing, 0.5),
        "onset_density": safe_float(density),
        "polyrhythm_flag": complexity > 0.7,
        "pass_details": results,
    }


def _bpm_confidence(results: list[dict]) -> float:
    bpms = [r["bpm"] for r in results if "bpm" in r and r["bpm"] > 0]
    if len(bpms) < 2:
        return 0.3
    spread = np.std(bpms) / (np.mean(bpms) + 1e-8)
    conf = max(0.0, min(1.0, 1.0 - spread * 5))
    return float(conf)


def _guess_time_signature(pp: PreprocessedAudio) -> str:
    """Heuristic time signature guess from tempogram periodicity."""
    try:
        tg = pp.tempogram
        if tg.size == 0:
            return "4/4"
        mean_profile = np.mean(tg, axis=1)
        if len(mean_profile) < 10:
            return "4/4"
        peak = np.argmax(mean_profile[1:]) + 1
        if peak % 3 == 0 and peak % 4 != 0:
            return "3/4"
        if peak % 6 == 0:
            return "6/8"
        return "4/4"
    except Exception:
        return "4/4"
