"""X — Motif / repetition analysis module."""
from __future__ import annotations

from typing import Any

import librosa
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from .preprocessing import PreprocessedAudio
from .utils import safe_float


def analyze_motif(pp: PreprocessedAudio) -> dict[str, Any]:
    """Detect repeating motifs using self-similarity on MFCC."""
    try:
        mfcc = librosa.feature.mfcc(y=pp.y_mono, sr=pp.sr, n_mfcc=13)

        hop_length = 512
        seg_len = int(2.0 * pp.sr / hop_length)
        n_frames = mfcc.shape[1]

        if n_frames < seg_len * 2:
            return _empty_motif("Audio too short for motif detection")

        segments = []
        positions = []
        step = max(1, seg_len // 2)
        for start in range(0, n_frames - seg_len, step):
            seg = mfcc[:, start : start + seg_len]
            segments.append(seg.mean(axis=1))
            positions.append(start)

        if len(segments) < 2:
            return _empty_motif("Not enough segments")

        seg_matrix = np.array(segments)
        sim = cosine_similarity(seg_matrix)
        np.fill_diagonal(sim, 0)

        n = sim.shape[0]
        for i in range(n):
            for j in range(n):
                if abs(i - j) <= 1:
                    sim[i, j] = 0

        threshold = 0.85
        pairs = []
        for i in range(n):
            for j in range(i + 2, n):
                if sim[i, j] >= threshold:
                    pairs.append((i, j, float(sim[i, j])))

        repetition_density = len(pairs) / (n * (n - 1) / 2 + 1e-8) if n > 1 else 0.0

        mean_self_sim = float(np.mean(sim[sim > 0])) if np.any(sim > 0) else 0.0

        unique_motifs = _count_unique_motifs(pairs, n)

        return {
            "repetition_density": safe_float(repetition_density),
            "mean_self_similarity": safe_float(mean_self_sim),
            "n_motif_pairs": len(pairs),
            "estimated_unique_motifs": unique_motifs,
            "motif_confidence": min(1.0, len(pairs) / 10.0) if pairs else 0.2,
            "notes": [],
        }

    except Exception as e:
        return _empty_motif(f"Motif analysis error: {e}")


def _count_unique_motifs(pairs: list[tuple], n: int) -> int:
    """Simple union-find to count distinct motif clusters."""
    if not pairs:
        return 0
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i, j, _ in pairs:
        union(i, j)

    roots = set()
    for i, j, _ in pairs:
        roots.add(find(i))
    return len(roots)


def _empty_motif(reason: str) -> dict[str, Any]:
    return {
        "repetition_density": 0.0,
        "mean_self_similarity": 0.0,
        "n_motif_pairs": 0,
        "estimated_unique_motifs": 0,
        "motif_confidence": 0.1,
        "notes": [reason],
    }
