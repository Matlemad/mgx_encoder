"""Load audio from local files."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import librosa
import numpy as np
import soundfile as sf


def load_audio(path: str | Path, sr: int = 22050) -> dict[str, Any]:
    """Load an audio file and return signal + metadata.

    Returns dict with keys: y, sr, duration_sec, original_sr, filename.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    info = sf.info(str(path))
    original_sr = info.samplerate
    duration_sec = info.duration

    y, loaded_sr = librosa.load(str(path), sr=sr, mono=True)

    return {
        "y": y,
        "sr": loaded_sr,
        "duration_sec": float(duration_sec),
        "original_sr": original_sr,
        "filename": path.name,
    }
