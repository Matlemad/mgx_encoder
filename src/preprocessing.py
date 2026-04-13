"""Preprocessing pipeline: HPSS, band splits, tuning, multi-chroma features."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import librosa
import numpy as np
from scipy.signal import butter, sosfilt


@dataclass
class PreprocessedAudio:
    """Container for all preprocessed signals and features."""
    y_mono: np.ndarray = field(repr=False)
    sr: int = 22050
    y_harmonic: np.ndarray = field(default_factory=lambda: np.array([]), repr=False)
    y_percussive: np.ndarray = field(default_factory=lambda: np.array([]), repr=False)
    y_low: np.ndarray = field(default_factory=lambda: np.array([]), repr=False)
    y_mid: np.ndarray = field(default_factory=lambda: np.array([]), repr=False)
    y_high: np.ndarray = field(default_factory=lambda: np.array([]), repr=False)
    onset_env: np.ndarray = field(default_factory=lambda: np.array([]), repr=False)
    chroma: np.ndarray = field(default_factory=lambda: np.array([]), repr=False)
    tempogram: np.ndarray = field(default_factory=lambda: np.array([]), repr=False)
    mel_spec: np.ndarray = field(default_factory=lambda: np.array([]), repr=False)
    duration_sec: float = 0.0
    # --- new fields for improved tonal analysis ---
    tuning_offset_cents: float = 0.0
    chroma_cqt: np.ndarray = field(default_factory=lambda: np.array([]), repr=False)
    chroma_stft: np.ndarray = field(default_factory=lambda: np.array([]), repr=False)
    chroma_cens: np.ndarray = field(default_factory=lambda: np.array([]), repr=False)
    chroma_cqt_harmonic: np.ndarray = field(default_factory=lambda: np.array([]), repr=False)
    chroma_cens_harmonic: np.ndarray = field(default_factory=lambda: np.array([]), repr=False)


def _bandpass(y: np.ndarray, sr: int, low: float, high: float, order: int = 4) -> np.ndarray:
    nyq = sr / 2.0
    low_n = max(low / nyq, 1e-5)
    high_n = min(high / nyq, 0.9999)
    if low_n >= high_n:
        return y
    sos = butter(order, [low_n, high_n], btype="band", output="sos")
    return sosfilt(sos, y).astype(np.float32)


def _lowpass(y: np.ndarray, sr: int, cutoff: float, order: int = 4) -> np.ndarray:
    nyq = sr / 2.0
    norm = min(cutoff / nyq, 0.9999)
    sos = butter(order, norm, btype="low", output="sos")
    return sosfilt(sos, y).astype(np.float32)


def _highpass(y: np.ndarray, sr: int, cutoff: float, order: int = 4) -> np.ndarray:
    nyq = sr / 2.0
    norm = max(cutoff / nyq, 1e-5)
    sos = butter(order, norm, btype="high", output="sos")
    return sosfilt(sos, y).astype(np.float32)


def _estimate_tuning(y: np.ndarray, sr: int) -> float:
    """Global tuning offset in cents via librosa.estimate_tuning."""
    try:
        tuning = librosa.estimate_tuning(y=y, sr=sr)
        if np.isfinite(tuning):
            return float(tuning * 100)
        return 0.0
    except Exception:
        return 0.0


def _compute_chromas(
    y_mono: np.ndarray,
    y_harmonic: np.ndarray,
    sr: int,
    tuning_cents: float,
) -> dict[str, np.ndarray]:
    """Compute multiple chroma representations with tuning correction.

    Returns dict with chroma_cqt, chroma_stft, chroma_cens (on mono)
    and chroma_cqt_harmonic, chroma_cens_harmonic (on harmonic).
    """
    tuning_hz = tuning_cents / 100.0

    chroma_cqt = librosa.feature.chroma_cqt(
        y=y_mono, sr=sr, tuning=tuning_hz, n_chroma=12,
    )
    chroma_stft = librosa.feature.chroma_stft(
        y=y_mono, sr=sr, tuning=tuning_hz, n_chroma=12,
    )
    chroma_cens = librosa.feature.chroma_cens(
        y=y_mono, sr=sr, tuning=tuning_hz, n_chroma=12,
    )

    chroma_cqt_h = librosa.feature.chroma_cqt(
        y=y_harmonic, sr=sr, tuning=tuning_hz, n_chroma=12,
    )
    chroma_cens_h = librosa.feature.chroma_cens(
        y=y_harmonic, sr=sr, tuning=tuning_hz, n_chroma=12,
    )

    return {
        "chroma_cqt": chroma_cqt,
        "chroma_stft": chroma_stft,
        "chroma_cens": chroma_cens,
        "chroma_cqt_harmonic": chroma_cqt_h,
        "chroma_cens_harmonic": chroma_cens_h,
    }


def preprocess(y: np.ndarray, sr: int = 22050) -> PreprocessedAudio:
    """Run full preprocessing pipeline on mono audio."""
    if y.ndim > 1:
        y = librosa.to_mono(y)

    y = librosa.util.normalize(y)
    y, _ = librosa.effects.trim(y, top_db=30)
    duration_sec = len(y) / sr

    tuning_cents = _estimate_tuning(y, sr)

    y_harmonic, y_percussive = librosa.effects.hpss(y)

    y_low = _lowpass(y, sr, 250)
    y_mid = _bandpass(y, sr, 250, 4000)
    y_high = _highpass(y, sr, 4000)

    onset_env = librosa.onset.onset_strength(y=y, sr=sr)

    chromas = _compute_chromas(y, y_harmonic, sr, tuning_cents)

    tempogram = librosa.feature.tempogram(onset_envelope=onset_env, sr=sr)
    mel_spec = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128)

    return PreprocessedAudio(
        y_mono=y,
        sr=sr,
        y_harmonic=y_harmonic,
        y_percussive=y_percussive,
        y_low=y_low,
        y_mid=y_mid,
        y_high=y_high,
        onset_env=onset_env,
        chroma=chromas["chroma_cqt_harmonic"],
        tempogram=tempogram,
        mel_spec=mel_spec,
        duration_sec=duration_sec,
        tuning_offset_cents=tuning_cents,
        chroma_cqt=chromas["chroma_cqt"],
        chroma_stft=chromas["chroma_stft"],
        chroma_cens=chromas["chroma_cens"],
        chroma_cqt_harmonic=chromas["chroma_cqt_harmonic"],
        chroma_cens_harmonic=chromas["chroma_cens_harmonic"],
    )
