"""MGX Lyrics Companion — guided songwriting flow."""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

import streamlit as st
import matplotlib
matplotlib.use("Agg")
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
from src.lyrics_editor import analyze_lyrics
from src.text_mining import mine_text, kwic
from src.inspiration_engine import generate_inspiration
from src.providers.mock_musixmatch import MockMusixmatch
from src.providers.mock_cyanite import MockCyanite
from src.contextual_palette.selection_analyzer import classify_selection, SelectionType
from src.contextual_palette.runner import run_all_for_selection, get_available_modules
from src.utils import save_json, save_text, ensure_dir, NumpyEncoder

OUTPUTS_DIR = Path(__file__).parent / "outputs"
TEMP_DIR = Path(__file__).parent / "temp"

st.set_page_config(page_title="MGX Lyrics Companion", layout="wide")

# ─── Session state ──────────────────────────────────────────────────────────
_DEFAULTS = {
    "mgx_output": None, "mgx_json_str": None, "mgx_report_text": None,
    "cyanite_result": None, "musixmatch_result": None,
    "lyrics_result": None, "mining_result": None, "inspiration_result": None,
    "flow_step": 1, "palette_results": None,
    "lyrics_saved": "",
    "R": None, "M": None, "H": None, "X": None, "F": None, "C_data": None,
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ─── Header ─────────────────────────────────────────────────────────────────
st.title("MGX Lyrics Companion")

step = st.session_state.flow_step
step_labels = ["1. Analyze Demo", "2. Text & Mining", "3. Inspiration Studio", "Export"]
step_icons = ["1️⃣", "2️⃣", "3️⃣", "📦"]
cols = st.columns(len(step_labels))
for i, (lbl, icon) in enumerate(zip(step_labels, step_icons), 1):
    with cols[i - 1]:
        if i < step:
            st.success(f"{icon} {lbl}")
        elif i == step:
            st.info(f"**{icon} {lbl}**")
        else:
            st.caption(f"{icon} {lbl}")

st.divider()


# ═════════════════════════════════════════════════════════════════════════════
# STEP 1 — ANALYZE DEMO
# ═════════════════════════════════════════════════════════════════════════════
if step == 1:
    st.header("Step 1 — Upload your demo and analyze it")
    st.caption("Upload the audio file of your demo (or paste a YouTube link). We'll extract the music genome and mock-enrich it with Cyanite.")

    col_file, col_yt = st.columns(2)
    with col_file:
        uploaded_file = st.file_uploader("WAV / MP3 / FLAC", type=["wav", "mp3", "flac"], key="audio_upload")
    with col_yt:
        yt_url = st.text_input("Or paste a YouTube link", key="yt_url")
        with st.expander("YouTube auth"):
            yt_browser = st.selectbox("Cookies from", ["auto-detect", "chrome", "firefox", "safari", "edge", "brave", "none"], key="yt_browser")
            yt_cookies_file = st.text_input("cookies.txt path", key="yt_cookies_file")

    run_btn = st.button("Analyze Demo", type="primary", use_container_width=True)

    if run_btn:
        ensure_dir(OUTPUTS_DIR); ensure_dir(TEMP_DIR)
        audio_path = None; source = "file"; yt_title = None; yt_url_used = None; meta_notes = []

        if uploaded_file is not None:
            tmp = TEMP_DIR / uploaded_file.name
            with open(tmp, "wb") as f: f.write(uploaded_file.getbuffer())
            audio_path = str(tmp)
        elif yt_url and yt_url.strip():
            if not is_valid_youtube_url(yt_url.strip()):
                st.error("Invalid YouTube URL."); st.stop()
            with st.spinner("Downloading from YouTube..."):
                try:
                    _br = yt_browser if yt_browser not in ("auto-detect","none") else None
                    _ck = yt_cookies_file.strip() or None
                    yt_result = download_audio_from_youtube(yt_url.strip(), output_dir=TEMP_DIR,
                        cookies_from_browser=_br if _br else None, cookies_file=_ck)
                    audio_path = yt_result["audio_path"]; yt_title = yt_result.get("title")
                    yt_url_used = yt_url.strip(); source = "youtube"
                except Exception as e:
                    st.error(f"YouTube download failed: {e}"); st.stop()
        else:
            st.info("Upload a file or paste a URL to continue."); st.stop()

        with st.spinner("Loading audio..."): audio_data = load_audio(audio_path)
        with st.spinner("Preprocessing..."): pp = preprocess(audio_data["y"], audio_data["sr"])

        progress = st.progress(0, text="Rhythm...")
        try: R = analyze_rhythm(pp)
        except Exception as e: R = {"error": str(e)}; meta_notes.append(str(e))
        progress.progress(15, text="Melody...")
        try: M = analyze_melody(pp)
        except Exception as e: M = {"error": str(e)}; meta_notes.append(str(e))
        progress.progress(30, text="Harmony...")
        try: H = analyze_harmony(pp)
        except Exception as e: H = {"error": str(e)}; meta_notes.append(str(e))
        progress.progress(50, text="Motifs...")
        try: X = analyze_motif(pp)
        except Exception as e: X = {"error": str(e)}; meta_notes.append(str(e))
        progress.progress(65, text="Form...")
        try: F = analyze_form(pp)
        except Exception as e: F = {"error": str(e)}; meta_notes.append(str(e))
        progress.progress(80, text="Confidence...")

        meta = {"source": source, "filename": audio_data["filename"], "youtube_url": yt_url_used,
                "title": yt_title, "duration_sec": round(audio_data["duration_sec"], 2),
                "sample_rate": audio_data["original_sr"], "analysis_sample_rate": audio_data["sr"], "notes": meta_notes}

        _NN = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
        _kc = H.get("key_center", H.get("key","C"))
        _ki = _NN.index(_kc) if _kc in _NN else 0
        _pc = np.array(M.get("pitch_class_histogram",[0.0]*12))
        _pcr = np.roll(_pc, -_ki); _s = _pcr.sum()
        if _s > 0: _pcr = _pcr / _s
        M["pitch_class_profile_relative"] = _pcr.tolist()

        C_data = compute_confidence(meta, R, M, H, X, F)
        def _strip(d): return {k:v for k,v in d.items() if k!="pass_details"}
        mgx_output = {"meta":meta,"R":_strip(R),"M":_strip(M),"H":_strip(H),"X":_strip(X),"F":_strip(F),"C":C_data}

        progress.progress(90, text="Cyanite enrichment (mock)...")
        mock_cy = MockCyanite()
        cy_data = mock_cy.analyze_audio(audio_path or "mock")
        cy_data["tags"] = mock_cy.similarity_tags(audio_path or "mock")

        progress.progress(100, text="Done!")
        save_json(mgx_output, OUTPUTS_DIR / "mgx_output.json")
        report_text = generate_report(mgx_output)
        save_text(report_text, OUTPUTS_DIR / "mgx_report.md")

        st.session_state.mgx_output = mgx_output
        st.session_state.mgx_json_str = json.dumps(mgx_output, indent=2, cls=NumpyEncoder, ensure_ascii=False)
        st.session_state.mgx_report_text = report_text
        st.session_state.cyanite_result = cy_data
        st.session_state.R = R; st.session_state.M = M; st.session_state.H = H
        st.session_state.X = X; st.session_state.F = F; st.session_state.C_data = C_data

    # Show results if available
    if st.session_state.mgx_output:
        mgx = st.session_state.mgx_output
        H = st.session_state.H; R = st.session_state.R
        cy = st.session_state.cyanite_result

        st.success("Demo analyzed!")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("BPM", f"{R.get('bpm','?'):.0f}" if isinstance(R.get('bpm'), (int,float)) else "?")
        kc = H.get("key_center", H.get("key","?")); km = H.get("key_mode", H.get("mode","?"))
        c2.metric("Key", f"{kc} {km}")
        c3.metric("Confidence", f"{st.session_state.C_data.get('overall_confidence',0):.0%}")
        if cy:
            c4.metric("Mood (mock)", cy.get("mood_primary", "?"))

        with st.expander("Full MGX details"):
            st.json(mgx)
        if cy:
            with st.expander("Cyanite enrichment (mock)"):
                st.json(cy)

        st.button("Continue to Step 2 →", on_click=lambda: st.session_state.update(flow_step=2), type="primary", use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# STEP 2 — TEXT & MINING
# ═════════════════════════════════════════════════════════════════════════════
elif step == 2:
    st.header("Step 2 — Paste your lyrics and run text mining")
    st.caption("Paste the lyrics that are sung on the demo. The system will analyze structure and language.")

    lyrics_text = st.text_area(
        "Your lyrics:", height=300,
        value=st.session_state.lyrics_saved,
        placeholder="Verse 1\nYour first line here\nSecond line\n\nChorus\nRepeat this line\nRepeat this line",
    )
    # Persist lyrics outside the widget so they survive step changes
    if lyrics_text != st.session_state.lyrics_saved:
        st.session_state.lyrics_saved = lyrics_text

    if lyrics_text and lyrics_text.strip():
        lr = analyze_lyrics(lyrics_text)
        st.session_state.lyrics_result = lr

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Lines", lr["n_lines"])
        c2.metric("Stanzas", lr["n_stanzas"])
        c3.metric("Words", lr["n_words"])
        rep = lr["repeated_lines"]
        c4.metric("Repeated lines", len(rep))

        if rep:
            with st.expander(f"Repeated lines ({len(rep)})"):
                for rl in rep:
                    st.text(f'  x{rl["count"]}  "{rl["line"]}"')

        run_mining = st.button("Run Text Mining", type="primary", use_container_width=True)
        if run_mining:
            mr = mine_text(lyrics_text)
            st.session_state.mining_result = mr

        if st.session_state.mining_result:
            mr = st.session_state.mining_result
            st.success(f"Mining done: {mr['n_filtered_tokens']} tokens (no stopwords)")
            col_f, col_b, col_c = st.columns(3)
            with col_f:
                st.markdown("**Top words**")
                for w, c in list(mr["word_frequencies"].items())[:12]:
                    st.text(f"  {c:3d}  {w}")
            with col_b:
                st.markdown("**Top bigrams**")
                for bg, c in list(mr["bigrams"].items())[:10]:
                    st.text(f"  {c:3d}  {bg}")
            with col_c:
                st.markdown("**Co-occurrences**")
                for pair, c in list(mr["cooccurrences"].items())[:10]:
                    st.text(f"  {c:3d}  {pair}")

            kw_input = st.text_input("KWIC search:", key="kwic_kw")
            if kw_input and kw_input.strip():
                for r in kwic(mr["tokens"], kw_input.strip())[:15]:
                    st.text(f"  ...{r['left']}  [{r['keyword']}]  {r['right']}...")

            st.button("Continue to Step 3 →", on_click=lambda: st.session_state.update(flow_step=3), type="primary", use_container_width=True)

    col_back, _ = st.columns([1, 3])
    with col_back:
        st.button("← Back to Step 1", on_click=lambda: st.session_state.update(flow_step=1))


# ═════════════════════════════════════════════════════════════════════════════
# STEP 3 — INSPIRATION STUDIO (with contextual palette)
# ═════════════════════════════════════════════════════════════════════════════
elif step == 3:
    st.header("Step 3 — Inspiration Studio")

    # ── Reference artists ──
    with st.expander("Reference artists & corpus", expanded=False):
        corpus_mode = st.selectbox("Corpus", ["All (global mock)", "Artist reference mode"], key="corpus_mode")
        ref_artists = st.text_input("Reference artists (comma separated)", key="ref_artists",
            placeholder="e.g. Joni Mitchell, Leonard Cohen")

        if st.button("Load corpus data"):
            mock_mx = MockMusixmatch()
            mining = st.session_state.mining_result or {}
            top_themes = list(mining.get("word_frequencies", {}).keys())[:5]
            mx_data = {"themes": mock_mx.search_by_theme(top_themes)}
            if corpus_mode == "Artist reference mode" and ref_artists.strip():
                mx_data["related_artists"] = []
                for a in [x.strip() for x in ref_artists.split(",") if x.strip()][:3]:
                    mx_data["related_artists"].extend(mock_mx.related_artists(a))
            st.session_state.musixmatch_result = mx_data

            mock_cy = MockCyanite()
            if not st.session_state.cyanite_result:
                st.session_state.cyanite_result = mock_cy.analyze_audio("mock")
            st.success("Corpus data loaded (mock).")

    # ── Main layout: lyrics + palette ──
    lyrics_text = st.session_state.lyrics_saved
    if not lyrics_text or not lyrics_text.strip():
        st.warning("No lyrics found. Go back to Step 2 and paste your lyrics.")
    else:
        col_editor, col_palette = st.columns([3, 2])

        with col_editor:
            st.markdown("#### Your lyrics")
            st.caption("Copy a word, phrase or stanza from below and paste it in the selection box underneath.")
            st.code(lyrics_text, language=None)

            selected_text = st.text_input(
                "Selection (paste here):",
                key="palette_selection",
                placeholder="e.g. broken heart  |  I walk the empty streets at night",
            )

        with col_palette:
            st.markdown("#### Contextual Palette")

            if selected_text and selected_text.strip():
                sel_type = classify_selection(selected_text, lyrics_text)
                st.caption(f"Selection type: **{sel_type.value}**")

                available = get_available_modules(sel_type)
                mod_names = [m.title for m in available]
                st.caption(f"{len(available)} tools available")

                if st.button("Analyze Selection", type="primary", use_container_width=True):
                    context = {
                        "mgx": st.session_state.mgx_output,
                        "cyanite": st.session_state.cyanite_result,
                        "musixmatch": st.session_state.musixmatch_result,
                        "mining": st.session_state.mining_result or {},
                    }
                    results = run_all_for_selection(selected_text, lyrics_text, context)
                    st.session_state.palette_results = results

                if st.session_state.palette_results:
                    res = st.session_state.palette_results
                    st.caption(f"Results for: \"{res.get('_selected_text', '')[:60]}...\"")

                    # ── Lexical Constellation ──
                    lc = res.get("lexical_constellation")
                    if lc:
                        with st.expander("🌐 Lexical Constellation", expanded=True):
                            local = lc.get("local_connections", [])
                            corpus = lc.get("corpus_connections", [])
                            if local:
                                st.markdown("**Local:** " + "  ".join(f"`{w}`" for w in local))
                            if corpus:
                                st.markdown("**Corpus:** " + "  ".join(f"`{w}`" for w in corpus))

                    # ── Rhyme Explorer ──
                    rh = res.get("rhyme_explorer")
                    if rh:
                        with st.expander("🎵 Rhyme Explorer"):
                            for cat in ["perfect_rhymes", "near_rhymes", "assonances", "consonances"]:
                                items = rh.get(cat, [])
                                if items:
                                    label = cat.replace("_", " ").title()
                                    st.markdown(f"**{label}:** " + "  ".join(f"`{w}`" for w in items))

                    # ── Metric Rewrite ──
                    mr = res.get("metric_rewrite")
                    if mr:
                        with st.expander("📐 Metric-Aware Rewrite"):
                            om = mr.get("original_metrics", {})
                            st.caption(f"Original: {om.get('syllables',0)} syl, {om.get('word_count',0)} words, ending: {om.get('ending_type','?')}")
                            for alt in mr.get("alternatives", []):
                                st.markdown(
                                    f"**[{alt['style']}]** {alt['text']}  \n"
                                    f"_{om.get('syllables',0)} syl → {alt['syllables']} syl (diff {alt['distance_score']})_"
                                )

                    # ── Emotional Reading ──
                    er = res.get("emotional_reading")
                    if er:
                        with st.expander("💎 Emotional Reading"):
                            c1, c2, c3 = st.columns(3)
                            c1.metric("Lyrics", er.get("lyrics_emotion","?"))
                            c2.metric("Music", er.get("music_emotion","?"))
                            c3.metric("Alignment", f"{er.get('alignment_score',0):.0%}")
                            for n in er.get("notes", []):
                                st.info(n)

                    # ── Corpus Insights ──
                    ci = res.get("corpus_insights")
                    if ci:
                        with st.expander("📚 Corpus Insights"):
                            common = ci.get("common_associations", [])
                            less = ci.get("less_common_directions", [])
                            if common:
                                st.markdown("**Common:** " + "  ".join(f"`{w}`" for w in common))
                            if less:
                                st.markdown("**Less explored:** " + "  ".join(f"`{w}`" for w in less))

                    # ── Cliche Detector ──
                    cd = res.get("cliche_detector")
                    if cd:
                        with st.expander("⚡ Cliche Detector"):
                            score = cd.get("cliche_score", 0)
                            if score > 70:
                                st.error(f"Cliche score: {score}/100")
                            elif score > 30:
                                st.warning(f"Cliche score: {score}/100")
                            else:
                                st.success(f"Cliche score: {score}/100 — looking fresh")
                            for r in cd.get("reasons", []):
                                st.caption(r)
                            alts = cd.get("alternatives", [])
                            if alts:
                                st.markdown("**Try instead:** " + "  ".join(f"`{a}`" for a in alts))

                    # ── Imagery Analyzer ──
                    ia = res.get("imagery_analyzer")
                    if ia and any(isinstance(v, (int, float)) and v > 0 for v in ia.values()):
                        with st.expander("👁 Imagery Analyzer"):
                            senses = ["visual", "auditory", "tactile", "spatial", "body"]
                            vals = [ia.get(s, 0) for s in senses]
                            if any(v > 0 for v in vals):
                                fig, ax = plt.subplots(figsize=(4, 4), subplot_kw=dict(polar=True))
                                angles = np.linspace(0, 2 * np.pi, len(senses), endpoint=False).tolist()
                                vals_plot = vals + [vals[0]]
                                angles += [angles[0]]
                                ax.fill(angles, vals_plot, alpha=0.25)
                                ax.plot(angles, vals_plot, linewidth=2)
                                ax.set_xticks(angles[:-1])
                                ax.set_xticklabels(senses, size=8)
                                ax.set_ylim(0, max(vals_plot) + 0.1)
                                st.pyplot(fig)
                                plt.close()
                            else:
                                st.caption("No sensory imagery detected in selection.")

                    # ── Narrative Function ──
                    nf = res.get("narrative_function")
                    if nf:
                        with st.expander("📖 Narrative Function"):
                            st.metric("Role", nf.get("detected_role", "?"))
                            st.caption(f"Confidence: {nf.get('confidence', 0):.0%}")
                            alts = nf.get("alternatives", [])
                            if alts:
                                st.caption(f"Alternatives: {', '.join(alts)}")

                    # ── Repetition Radar ──
                    rr = res.get("repetition_radar")
                    if rr:
                        with st.expander("🔁 Repetition Radar"):
                            rw = rr.get("repeated_words", [])
                            if rw:
                                st.markdown("**Repeated:** " + "  ".join(f"`{w['word']}` x{w['count']}" for w in rw[:10]))
                            syms = rr.get("repeated_symbols", [])
                            if syms:
                                st.markdown("**Symbolic fields:** " + "  ".join(f"`{s}`" for s in syms))

                    # ── Inspiration Directions ──
                    idir = res.get("inspiration_directions")
                    if idir:
                        with st.expander("✨ Inspiration Directions", expanded=True):
                            ue = idir.get("underexplored_territories", [])
                            if ue:
                                st.markdown("**Underexplored:** " + "  ".join(f"`{t}`" for t in ue))
                            so = idir.get("symbolic_opportunities", [])
                            for s in so:
                                st.info(s)
                            for p in idir.get("creative_prompts", []):
                                st.success(p)

            else:
                st.caption("Select text from your lyrics to activate the palette.")

    st.divider()
    col_back, col_fwd = st.columns(2)
    with col_back:
        st.button("← Back to Step 2", on_click=lambda: st.session_state.update(flow_step=2))
    with col_fwd:
        st.button("Go to Export →", on_click=lambda: st.session_state.update(flow_step=4), type="primary")


# ═════════════════════════════════════════════════════════════════════════════
# STEP 4 — EXPORT
# ═════════════════════════════════════════════════════════════════════════════
elif step == 4:
    st.header("Export")
    ensure_dir(OUTPUTS_DIR)

    has_mgx = st.session_state.mgx_output is not None
    has_mining = st.session_state.mining_result is not None
    has_palette = st.session_state.palette_results is not None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("MGX", "ready" if has_mgx else "—")
    c2.metric("Text Mining", "ready" if has_mining else "—")
    c3.metric("Palette", "ready" if has_palette else "—")
    c4.metric("Full Project", "ready" if (has_mgx or has_mining) else "—")

    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        if has_mgx:
            st.download_button("MGX JSON", st.session_state.mgx_json_str,
                file_name="mgx_output.json", mime="application/json", use_container_width=True)
        if has_mgx and st.session_state.mgx_report_text:
            st.download_button("MGX Report", st.session_state.mgx_report_text,
                file_name="mgx_report.md", mime="text/markdown", use_container_width=True)
    with col_b:
        if has_mining:
            st.download_button("Lyrics Mining JSON",
                json.dumps(st.session_state.mining_result, indent=2, ensure_ascii=False),
                file_name="lyrics_mining.json", mime="application/json", use_container_width=True)

    # Full project
    if has_mgx or has_mining:
        st.divider()
        full = {
            "mgx": st.session_state.mgx_output or {},
            "lyrics": st.session_state.lyrics_result or {},
            "text_mining": st.session_state.mining_result or {},
            "cyanite": st.session_state.cyanite_result or {},
            "musixmatch": st.session_state.musixmatch_result or {},
            "inspiration": st.session_state.inspiration_result or {},
            "palette_last": st.session_state.palette_results or {},
        }
        st.download_button("Download Full Project JSON",
            json.dumps(full, indent=2, cls=NumpyEncoder, ensure_ascii=False),
            file_name="full_project.json", mime="application/json", use_container_width=True)

    st.divider()
    st.button("← Back to Studio", on_click=lambda: st.session_state.update(flow_step=3))
