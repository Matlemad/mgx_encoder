"""F — Form / structure analysis module."""
from __future__ import annotations

from typing import Any

import librosa
import numpy as np
from sklearn.cluster import AgglomerativeClustering
from scipy.spatial.distance import squareform
from sklearn.metrics.pairwise import cosine_similarity

from .preprocessing import PreprocessedAudio
from .utils import safe_float, safe_list


def analyze_form(pp: PreprocessedAudio) -> dict[str, Any]:
    """Detect song structure (sections) from self-similarity."""
    try:
        chroma = pp.chroma
        mfcc = librosa.feature.mfcc(y=pp.y_mono, sr=pp.sr, n_mfcc=13)

        hop_length = 512
        beat_seg = int(4.0 * pp.sr / hop_length)
        n_frames = chroma.shape[1]

        if n_frames < beat_seg * 3:
            return _empty_form("Audio too short for form analysis")

        segments_chroma = []
        segments_mfcc = []
        positions = []
        for start in range(0, n_frames - beat_seg, beat_seg):
            c_seg = chroma[:, start : start + beat_seg].mean(axis=1)
            m_seg = mfcc[:, min(start, mfcc.shape[1] - 1) : min(start + beat_seg, mfcc.shape[1])].mean(axis=1)
            segments_chroma.append(c_seg)
            segments_mfcc.append(m_seg)
            positions.append(start)

        if len(segments_chroma) < 3:
            return _empty_form("Not enough segments for clustering")

        feat = np.hstack([np.array(segments_chroma), np.array(segments_mfcc)])
        sim = cosine_similarity(feat)
        dist = 1.0 - sim
        np.fill_diagonal(dist, 0)
        dist = np.clip(dist, 0, None)

        n_clusters = min(max(2, len(segments_chroma) // 3), 8)
        clustering = AgglomerativeClustering(
            n_clusters=n_clusters,
            metric="precomputed",
            linkage="average",
        )
        labels = clustering.fit_predict(dist)

        sec_per_frame = hop_length / pp.sr
        sections = []
        current_label = labels[0]
        section_start = 0
        for i in range(1, len(labels)):
            if labels[i] != current_label:
                sections.append({
                    "label": f"S{int(current_label)}",
                    "start_sec": round(positions[section_start] * sec_per_frame, 2),
                    "end_sec": round(positions[i] * sec_per_frame, 2),
                })
                current_label = labels[i]
                section_start = i
        sections.append({
            "label": f"S{int(current_label)}",
            "start_sec": round(positions[section_start] * sec_per_frame, 2),
            "end_sec": round(pp.duration_sec, 2),
        })

        label_sequence = [s["label"] for s in sections]
        unique_sections = len(set(label_sequence))

        repetition = 1.0 - (unique_sections / len(label_sequence)) if label_sequence else 0.0

        return {
            "sections": sections,
            "section_sequence": label_sequence,
            "n_sections": len(sections),
            "n_unique_sections": unique_sections,
            "structural_repetition": safe_float(repetition),
            "form_confidence": min(1.0, 0.3 + 0.1 * len(sections)),
            "notes": [],
        }

    except Exception as e:
        return _empty_form(f"Form analysis error: {e}")


def _empty_form(reason: str) -> dict[str, Any]:
    return {
        "sections": [],
        "section_sequence": [],
        "n_sections": 0,
        "n_unique_sections": 0,
        "structural_repetition": 0.0,
        "form_confidence": 0.1,
        "notes": [reason],
    }
