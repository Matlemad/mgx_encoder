"""Utility functions for MGX Encoder."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np


class NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy types."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_json(data: dict, path: str | Path) -> Path:
    p = Path(path)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, cls=NumpyEncoder, ensure_ascii=False)
    return p


def save_text(text: str, path: str | Path) -> Path:
    p = Path(path)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def safe_float(val: Any, default: float = 0.0) -> float:
    try:
        v = float(val)
        if np.isnan(v) or np.isinf(v):
            return default
        return v
    except (TypeError, ValueError):
        return default


def safe_list(arr: Any, max_len: int = 500) -> list:
    """Convert array-like to a JSON-safe list, capped in length."""
    try:
        lst = np.asarray(arr).tolist()
        if isinstance(lst, list) and len(lst) > max_len:
            return lst[:max_len]
        return lst
    except Exception:
        return []
