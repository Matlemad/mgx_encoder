"""Multi-pass analysis: run feature extraction on different signal views."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import librosa
import numpy as np

from .preprocessing import PreprocessedAudio


def _onset_enhanced(pp: PreprocessedAudio) -> np.ndarray:
    """Create onset-enhanced signal by multiplying mono with its onset envelope."""
    env = librosa.onset.onset_strength(y=pp.y_mono, sr=pp.sr)
    env_stretched = np.interp(
        np.linspace(0, len(env) - 1, len(pp.y_mono)),
        np.arange(len(env)),
        env,
    )
    env_stretched = env_stretched / (env_stretched.max() + 1e-8)
    return pp.y_mono * (0.5 + 0.5 * env_stretched)


def get_pass_signals(pp: PreprocessedAudio) -> dict[str, np.ndarray]:
    """Return the six pass signals."""
    return {
        "A_mono": pp.y_mono,
        "B_harmonic": pp.y_harmonic,
        "C_percussive": pp.y_percussive,
        "D_low": pp.y_low,
        "E_midhigh": pp.y_mid + pp.y_high,
        "F_onset": _onset_enhanced(pp),
    }


def run_on_passes(
    pp: PreprocessedAudio,
    pass_keys: list[str],
    fn: Callable[[np.ndarray, int], dict[str, Any]],
) -> list[dict[str, Any]]:
    """Run a feature-extraction function on the specified passes."""
    signals = get_pass_signals(pp)
    results = []
    for key in pass_keys:
        sig = signals.get(key)
        if sig is None or len(sig) == 0:
            continue
        try:
            out = fn(sig, pp.sr)
            out["_pass"] = key
            results.append(out)
        except Exception as e:
            results.append({"_pass": key, "_error": str(e)})
    return results


def aggregate_numeric(results: list[dict], field: str, weights: list[float] | None = None) -> float:
    """Weighted aggregation of a numeric field across pass results."""
    vals = []
    for r in results:
        v = r.get(field)
        if v is not None and isinstance(v, (int, float)) and np.isfinite(v):
            vals.append(float(v))

    if not vals:
        return 0.0

    if weights and len(weights) == len(vals):
        return float(np.average(vals, weights=weights))
    return float(np.mean(vals))
