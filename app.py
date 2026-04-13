"""MGX Encoder — Streamlit app."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import traceback
from pathlib import Path

import streamlit as st
import matplotlib.pyplot as plt
import numpy as np
import librosa
import librosa.display

from src.audio_loader import load_audio
from src.youtube_loader import download_audio_from_youtube, is_valid_youtube_url
from src.preprocessing import preprocess
from src.rhythm import analyze_rhythm
from src.melody import analyze_melody
from src.harmony import analyze_harmony
from src.motif import analyze_motif
from src.form import analyze_form
from src.confidence import compute_confidence
from src.report import generate_report
from src.utils import save_json, save_text, ensure_dir, NumpyEncoder

OUTPUTS_DIR = Path(__file__).parent / "outputs"
TEMP_DIR = Path(__file__).parent / "temp"

st.set_page_config(page_title="MGX Encoder", layout="wide")
st.title("MGX Encoder")
st.markdown(
    "Structural music genome extractor from a final stereo mix. "
    "Upload a file or paste a YouTube URL to generate an **MGX-v1** fingerprint."
)

st.divider()

col_file, col_yt = st.columns(2)
with col_file:
    st.subheader("Option 1: Upload Audio")
    uploaded_file = st.file_uploader(
        "WAV / MP3 / FLAC", type=["wav", "mp3", "flac"], key="audio_upload"
    )
with col_yt:
    st.subheader("Option 2: YouTube URL")
    yt_url = st.text_input("Paste a YouTube link", key="yt_url")
    with st.expander("YouTube authentication (if needed)"):
        st.caption(
            "YouTube may block downloads without authentication. "
            "Choose **one** option below."
        )
        yt_browser = st.selectbox(
            "Load cookies from browser",
            ["auto-detect", "chrome", "firefox", "safari", "edge", "brave", "none"],
            index=0,
            key="yt_browser",
        )
        yt_cookies_file = st.text_input(
            "Or path to cookies.txt file (Netscape format)",
            key="yt_cookies_file",
        )

st.divider()

col_opt1, col_opt2 = st.columns(2)
with col_opt1:
    save_plots = st.checkbox("Save debug plots", value=False)
with col_opt2:
    show_passes = st.checkbox("Show intermediate pass details", value=False)

run = st.button("Run MGX Encoding", type="primary", use_container_width=True)

if run:
    ensure_dir(OUTPUTS_DIR)
    ensure_dir(TEMP_DIR)

    audio_path: str | None = None
    source = "file"
    yt_title: str | None = None
    yt_url_used: str | None = None
    meta_notes: list[str] = []

    # --- Input resolution ---
    if uploaded_file is not None and yt_url.strip():
        st.warning("Both file and URL provided — using uploaded file.")

    if uploaded_file is not None:
        tmp = TEMP_DIR / uploaded_file.name
        with open(tmp, "wb") as f:
            f.write(uploaded_file.getbuffer())
        audio_path = str(tmp)
        source = "file"
    elif yt_url.strip():
        if not is_valid_youtube_url(yt_url.strip()):
            st.error("Invalid YouTube URL.")
            st.stop()
        with st.spinner("Downloading audio from YouTube..."):
            try:
                _browser = yt_browser if yt_browser not in ("auto-detect", "none") else None
                _cookies = yt_cookies_file.strip() if yt_cookies_file.strip() else None
                if yt_browser == "none":
                    _browser = ""  # explicitly skip auto-detect
                yt_result = download_audio_from_youtube(
                    yt_url.strip(),
                    output_dir=TEMP_DIR,
                    cookies_from_browser=_browser if _browser else None,
                    cookies_file=_cookies,
                )
                audio_path = yt_result["audio_path"]
                yt_title = yt_result.get("title")
                yt_url_used = yt_url.strip()
                source = "youtube"
            except Exception as e:
                st.error(f"YouTube download failed: {e}")
                st.info(
                    "**Tip**: YouTube often requires authentication. Try selecting your browser "
                    "in the authentication expander above, or provide a cookies.txt file. "
                    "See [yt-dlp FAQ](https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp)."
                )
                st.stop()
    else:
        st.info("Please upload an audio file or paste a YouTube URL.")
        st.stop()

    # --- Load & preprocess ---
    with st.spinner("Loading audio..."):
        try:
            audio_data = load_audio(audio_path)
        except Exception as e:
            st.error(f"Failed to load audio: {e}")
            st.stop()

    with st.spinner("Preprocessing (HPSS, band splits, features)..."):
        try:
            pp = preprocess(audio_data["y"], audio_data["sr"])
        except Exception as e:
            st.error(f"Preprocessing failed: {e}")
            meta_notes.append(f"Preprocessing error: {e}")
            st.stop()

    # --- Analysis ---
    progress = st.progress(0, text="Analyzing rhythm...")

    try:
        R = analyze_rhythm(pp)
    except Exception as e:
        R = {"error": str(e)}
        meta_notes.append(f"Rhythm error: {e}")
    progress.progress(20, text="Analyzing melody...")

    try:
        M = analyze_melody(pp)
    except Exception as e:
        M = {"error": str(e)}
        meta_notes.append(f"Melody error: {e}")
    progress.progress(40, text="Analyzing harmony...")

    try:
        H = analyze_harmony(pp)
    except Exception as e:
        H = {"error": str(e)}
        meta_notes.append(f"Harmony error: {e}")
    progress.progress(60, text="Analyzing motifs...")

    try:
        X = analyze_motif(pp)
    except Exception as e:
        X = {"error": str(e)}
        meta_notes.append(f"Motif error: {e}")
    progress.progress(80, text="Analyzing form...")

    try:
        F = analyze_form(pp)
    except Exception as e:
        F = {"error": str(e)}
        meta_notes.append(f"Form error: {e}")
    progress.progress(90, text="Computing confidence...")

    meta = {
        "source": source,
        "filename": audio_data["filename"],
        "youtube_url": yt_url_used,
        "title": yt_title,
        "duration_sec": round(audio_data["duration_sec"], 2),
        "sample_rate": audio_data["original_sr"],
        "analysis_sample_rate": audio_data["sr"],
        "notes": meta_notes,
    }

    # --- Post-process: inject key-relative melody profile ---
    _NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    _key_center = H.get("key_center", H.get("key", "C"))
    _key_idx = _NOTE_NAMES.index(_key_center) if _key_center in _NOTE_NAMES else 0
    _pc_hist = np.array(M.get("pitch_class_histogram", [0.0] * 12))
    _pc_rel = np.roll(_pc_hist, -_key_idx)
    _pc_rel_sum = _pc_rel.sum()
    if _pc_rel_sum > 0:
        _pc_rel = _pc_rel / _pc_rel_sum
    M["pitch_class_profile_relative"] = _pc_rel.tolist()

    C = compute_confidence(meta, R, M, H, X, F)

    # Strip pass_details from export (keep for UI)
    def _strip_passes(d: dict) -> dict:
        return {k: v for k, v in d.items() if k != "pass_details"}

    mgx_output = {
        "meta": meta,
        "R": _strip_passes(R),
        "M": _strip_passes(M),
        "H": _strip_passes(H),
        "X": _strip_passes(X),
        "F": _strip_passes(F),
        "C": C,
    }

    progress.progress(100, text="Done!")

    # --- Save outputs ---
    json_path = save_json(mgx_output, OUTPUTS_DIR / "mgx_output.json")
    report_text = generate_report(mgx_output)
    report_path = save_text(report_text, OUTPUTS_DIR / "mgx_report.md")

    # --- Debug plots ---
    if save_plots:
        fig_dir = ensure_dir(OUTPUTS_DIR / "plots")

        fig, axes = plt.subplots(3, 1, figsize=(12, 8))
        librosa.display.waveshow(pp.y_mono, sr=pp.sr, ax=axes[0])
        axes[0].set_title("Waveform (mono)")
        librosa.display.specshow(
            librosa.amplitude_to_db(pp.mel_spec, ref=np.max),
            sr=pp.sr, x_axis="time", y_axis="mel", ax=axes[1],
        )
        axes[1].set_title("Mel Spectrogram")
        librosa.display.specshow(pp.chroma, y_axis="chroma", x_axis="time", sr=pp.sr, ax=axes[2])
        axes[2].set_title("Chroma")
        plt.tight_layout()
        plt.savefig(fig_dir / "overview.png", dpi=100)
        plt.close()

    # --- Display results ---
    st.success("MGX-v1 encoding complete!")

    st.subheader("Metadata")
    st.json(meta)

    tab_r, tab_m, tab_h, tab_x, tab_f, tab_c = st.tabs(
        ["R — Rhythm", "M — Melody", "H — Harmony", "X — Motif", "F — Form", "C — Confidence"]
    )

    with tab_r:
        st.metric("BPM", f"{R.get('bpm', 'N/A')}")
        col1, col2, col3 = st.columns(3)
        col1.metric("Time Sig", R.get("time_signature", "?"))
        col2.metric("Beat Regularity", f"{R.get('beat_regularity', 0):.2f}")
        col3.metric("Groove Complexity", f"{R.get('groove_complexity', 0):.2f}")
        if show_passes and "pass_details" in R:
            st.json(R["pass_details"])

    with tab_m:
        col1, col2, col3 = st.columns(3)
        col1.metric("Pitch Range", f"{M.get('pitch_range_hz', 0):.0f} Hz")
        col2.metric("Mean Pitch", f"{M.get('pitch_mean_hz', 0):.0f} Hz")
        col3.metric("Voiced Ratio", f"{M.get('voiced_ratio', 0):.2f}")
        col1, col2, col3 = st.columns(3)
        col1.metric("Mean Interval", f"{M.get('mean_interval_semitones', 0):.1f} st")
        col2.metric("Stepwise Ratio", f"{M.get('stepwise_ratio', 0):.2f}")
        col3.metric("Vocal Likelihood", f"{M.get('vocal_likelihood', 0):.2f}")
        contour = M.get("contour_symbols", [])
        if contour:
            st.caption(f"Contour (first 60): {''.join(contour[:60])}")
        bg = M.get("contour_bigrams", {})
        if bg and any(v > 0 for v in bg.values()):
            fig_bg, ax_bg = plt.subplots(figsize=(6, 2.5))
            ax_bg.bar(bg.keys(), bg.values())
            ax_bg.set_ylabel("Frequency")
            ax_bg.set_title("Contour Bigrams (arrangement-invariant)")
            st.pyplot(fig_bg)
            plt.close()
        if show_passes and "pass_details" in M:
            st.json(M["pass_details"])

    with tab_h:
        key_center = H.get("key_center", H.get("key", "?"))
        key_mode = H.get("key_mode", H.get("mode", "?"))
        st.metric("Key Center", f"{key_center} {key_mode}")
        col1, col2, col3 = st.columns(3)
        col1.metric("Key Confidence", f"{H.get('key_confidence', H.get('mode_confidence', 0)):.2f}")
        col2.metric("Mode Ambiguity", H.get("mode_ambiguity", "N/A"))
        col3.metric("Tuning Offset", f"{H.get('tuning_offset_cents', 0):+.1f} ct")

        candidates = H.get("key_candidates", [])
        if candidates:
            st.caption("Top key candidates:")
            for c in candidates[:3]:
                st.text(f"  {c['key']} {c['mode']}  score={c['score']:.4f}")

        col1, col2 = st.columns(2)
        col1.metric("Chord Confidence", f"{H.get('chord_confidence', 0):.2f}")
        tier_labels = {1: "Full chords", 2: "Root only", 3: "Emphasis only"}
        col2.metric("Chord Tier", tier_labels.get(H.get("chord_tier"), "N/A"))

        chord_seq = H.get("chord_sequence", [])
        root_seq = H.get("root_sequence", [])
        if chord_seq:
            st.caption(f"Chords: {' | '.join(chord_seq[:24])}")
        elif root_seq:
            st.caption(f"Roots: {' | '.join(root_seq[:24])}")

        rel_roots = H.get("relative_root_functions", [])
        rel_chords = H.get("relative_chord_functions", [])
        if rel_chords:
            st.caption(f"Relative chords: {' | '.join(rel_chords[:20])}")
        elif rel_roots:
            st.caption(f"Relative roots: {' | '.join(rel_roots[:20])}")
        hr_pb = H.get("harmonic_rhythm_per_beat")
        if hr_pb is not None:
            st.metric("Harm. Rhythm (chg/beat)", f"{hr_pb:.3f}")

        h_notes = H.get("notes", [])
        if h_notes:
            for n in h_notes:
                st.info(n)

        if "chroma_profile" in H:
            note_names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
            fig, ax = plt.subplots(figsize=(8, 3))
            ax.bar(note_names, H["chroma_profile"])
            ax.set_ylabel("Energy")
            ax.set_title("Chroma Profile")
            st.pyplot(fig)
            plt.close()
        if show_passes and "pass_details" in H:
            st.json(H["pass_details"])

    with tab_x:
        col1, col2 = st.columns(2)
        col1.metric("Motif Pairs", X.get("n_motif_pairs", 0))
        col2.metric("Unique Motifs", X.get("estimated_unique_motifs", 0))
        col1, col2 = st.columns(2)
        col1.metric("Rep. Density", f"{X.get('repetition_density', 0):.4f}")
        col2.metric("Self-Similarity", f"{X.get('mean_self_similarity', 0):.2f}")

    with tab_f:
        col1, col2 = st.columns(2)
        col1.metric("Sections", F.get("n_sections", 0))
        col2.metric("Unique Types", F.get("n_unique_sections", 0))
        seq = F.get("section_sequence", [])
        if seq:
            st.markdown(f"**Sequence**: {' → '.join(seq)}")
        if F.get("sections"):
            st.table(F["sections"])

    with tab_c:
        col1, col2 = st.columns(2)
        col1.metric("Overall Confidence", f"{C.get('overall_confidence', 0):.2f}")
        mh_agr = C.get("melody_harmony_agreement")
        if mh_agr is not None:
            col2.metric("Melody/Harmony Agreement", f"{mh_agr:.2f}")
        fc = C.get("field_confidence", {})
        if fc:
            cols = st.columns(len(fc))
            for col, (field, score) in zip(cols, fc.items()):
                col.metric(field.capitalize(), f"{score:.2f}")
        if C.get("warnings"):
            st.warning("\n".join(f"- {w}" for w in C["warnings"]))
        st.info(C.get("disclaimer", ""))

    # --- Download buttons ---
    st.divider()
    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        with open(json_path, "r") as f:
            st.download_button(
                "Download MGX JSON",
                f.read(),
                file_name="mgx_output.json",
                mime="application/json",
                use_container_width=True,
            )
    with col_dl2:
        st.download_button(
            "Download Report (Markdown)",
            report_text,
            file_name="mgx_report.md",
            mime="text/markdown",
            use_container_width=True,
        )

    if save_plots and (OUTPUTS_DIR / "plots" / "overview.png").exists():
        st.subheader("Debug Plots")
        st.image(str(OUTPUTS_DIR / "plots" / "overview.png"))
