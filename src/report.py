"""Generate MGX report in Markdown format."""
from __future__ import annotations

from typing import Any
from datetime import datetime


def generate_report(mgx: dict[str, Any]) -> str:
    """Generate a human-readable Markdown report from MGX-v1 output."""
    lines: list[str] = []
    lines.append("# MGX-v1 Report")
    lines.append(f"\n_Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_\n")

    meta = mgx.get("meta", {})
    lines.append("## Metadata")
    lines.append(f"- **Source**: {meta.get('source', 'unknown')}")
    lines.append(f"- **Filename**: {meta.get('filename', 'N/A')}")
    if meta.get("title"):
        lines.append(f"- **Title**: {meta['title']}")
    lines.append(f"- **Duration**: {meta.get('duration_sec', 0):.1f}s")
    lines.append(f"- **Sample Rate**: {meta.get('sample_rate', 'N/A')} Hz")
    lines.append(f"- **Analysis SR**: {meta.get('analysis_sample_rate', 22050)} Hz")
    lines.append("")

    R = mgx.get("R", {})
    lines.append("## R — Rhythm")
    lines.append(f"- **BPM**: {R.get('bpm', 'N/A')}")
    lines.append(f"- **Time Signature**: {R.get('time_signature', 'N/A')}")
    lines.append(f"- **Beat Regularity**: {R.get('beat_regularity', 0):.2f}")
    lines.append(f"- **Groove Complexity**: {R.get('groove_complexity', 0):.2f}")
    lines.append(f"- **Swing Ratio**: {R.get('swing_ratio', 0):.2f}")
    lines.append(f"- **BPM Confidence**: {R.get('bpm_confidence', 0):.2f}")
    lines.append("")

    M = mgx.get("M", {})
    lines.append("## M — Melody")
    lines.append(f"- **Pitch Range**: {M.get('pitch_range_hz', 0):.1f} Hz")
    lines.append(f"- **Mean Pitch**: {M.get('pitch_mean_hz', 0):.1f} Hz")
    lines.append(f"- **Mean Interval**: {M.get('mean_interval_semitones', 0):.2f} semitones")
    lines.append(f"- **Contour Direction**: {M.get('contour_direction', 0):.2f}")
    lines.append(f"- **Stepwise Ratio**: {M.get('stepwise_ratio', 0):.2f}")
    lines.append(f"- **Voiced Ratio**: {M.get('voiced_ratio', 0):.2f}")
    lines.append(f"- **Vocal Likelihood**: {M.get('vocal_likelihood', 0):.2f}")
    lines.append(f"- **Pitch Confidence**: {M.get('pitch_confidence', 0):.2f}")

    bg = M.get("contour_bigrams")
    if bg:
        top_bg = sorted(bg.items(), key=lambda x: x[1], reverse=True)[:3]
        bg_str = ", ".join(f"{k}={v:.2f}" for k, v in top_bg)
        lines.append(f"- **Top Contour Bigrams**: {bg_str}")
    lines.append("")

    H = mgx.get("H", {})
    lines.append("## H — Harmony")

    key_center = H.get("key_center", H.get("key", "N/A"))
    key_mode = H.get("key_mode", H.get("mode", "N/A"))
    lines.append(f"- **Key Center**: {key_center}")
    lines.append(f"- **Mode**: {key_mode}")
    lines.append(f"- **Key Confidence**: {H.get('key_confidence', H.get('mode_confidence', 0)):.2f}")

    mode_amb = H.get("mode_ambiguity", "")
    if mode_amb:
        lines.append(f"- **Mode Ambiguity**: {mode_amb}")

    tuning = H.get("tuning_offset_cents", 0)
    lines.append(f"- **Tuning Offset**: {tuning:+.1f} cents")

    candidates = H.get("key_candidates", [])
    if candidates:
        lines.append("- **Key Candidates**:")
        for c in candidates[:3]:
            lines.append(f"  - {c['key']} {c['mode']}: {c['score']:.4f}")

    lines.append(f"- **Harmonic Change Rate**: {H.get('harmonic_change_rate', 0):.4f}")
    lines.append(f"- **Chroma Entropy**: {H.get('chroma_entropy', 0):.2f}")

    chord_tier = H.get("chord_tier")
    if chord_tier is not None:
        tier_label = {1: "Full chords", 2: "Root sequence only", 3: "Emphasis only"}.get(chord_tier, "?")
        lines.append(f"- **Chord Estimation Tier**: {chord_tier} ({tier_label})")
        lines.append(f"- **Chord Confidence**: {H.get('chord_confidence', 0):.2f}")

    chord_seq = H.get("chord_sequence", [])
    if chord_seq:
        lines.append(f"- **Chord Sequence**: {' | '.join(chord_seq[:32])}")

    root_seq = H.get("root_sequence", [])
    if root_seq and not chord_seq:
        lines.append(f"- **Root Sequence**: {' | '.join(root_seq[:32])}")

    sw_key = H.get("section_weighted_key")
    if sw_key:
        lines.append(f"- **Section-Weighted Key**: {sw_key.get('key', '?')} {sw_key.get('mode', '?')} (score {sw_key.get('score', 0):.3f})")

    rel_roots = H.get("relative_root_functions", [])
    if rel_roots:
        lines.append(f"- **Relative Root Functions**: {' | '.join(rel_roots[:24])}")
    rel_chords = H.get("relative_chord_functions", [])
    if rel_chords:
        lines.append(f"- **Relative Chord Functions**: {' | '.join(rel_chords[:24])}")
    hr_pb = H.get("harmonic_rhythm_per_beat")
    if hr_pb is not None:
        lines.append(f"- **Harmonic Rhythm (changes/beat)**: {hr_pb:.3f}")

    h_notes = H.get("notes", [])
    if h_notes:
        for n in h_notes:
            lines.append(f"  - _Note_: {n}")

    lines.append("")

    X = mgx.get("X", {})
    lines.append("## X — Motif")
    lines.append(f"- **Repetition Density**: {X.get('repetition_density', 0):.4f}")
    lines.append(f"- **Mean Self-Similarity**: {X.get('mean_self_similarity', 0):.2f}")
    lines.append(f"- **Motif Pairs Found**: {X.get('n_motif_pairs', 0)}")
    lines.append(f"- **Estimated Unique Motifs**: {X.get('estimated_unique_motifs', 0)}")
    lines.append(f"- **Motif Confidence**: {X.get('motif_confidence', 0):.2f}")
    lines.append("")

    F = mgx.get("F", {})
    lines.append("## F — Form")
    lines.append(f"- **Sections Detected**: {F.get('n_sections', 0)}")
    lines.append(f"- **Unique Section Types**: {F.get('n_unique_sections', 0)}")
    lines.append(f"- **Structural Repetition**: {F.get('structural_repetition', 0):.2f}")
    seq = F.get("section_sequence", [])
    if seq:
        lines.append(f"- **Section Sequence**: {' -> '.join(seq)}")
    lines.append(f"- **Form Confidence**: {F.get('form_confidence', 0):.2f}")
    lines.append("")

    C = mgx.get("C", {})
    lines.append("## C — Confidence")
    lines.append(f"- **Overall Confidence**: {C.get('overall_confidence', 0):.2f}")
    mh_agr = C.get("melody_harmony_agreement")
    if mh_agr is not None:
        lines.append(f"- **Melody/Harmony Agreement**: {mh_agr:.2f}")
    fc = C.get("field_confidence", {})
    for field, score in fc.items():
        lines.append(f"  - {field}: {score:.2f}")
    lines.append("")

    warnings = C.get("warnings", [])
    if warnings:
        lines.append("## Warnings")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    notes = C.get("notes", [])
    if notes:
        lines.append("## Notes")
        for n in notes:
            lines.append(f"- {n}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "> **Disclaimer**: " + C.get(
            "disclaimer",
            "This output is a structural similarity aid derived from final mixed audio only. "
            "It is not a legal proof of plagiarism or authorship.",
        )
    )
    lines.append("")

    return "\n".join(lines)
