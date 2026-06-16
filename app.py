"""MGX Librettist — melody-aware AI lyrics companion for songwriters."""
from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

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
from src.lyrics_editor import analyze_lyrics, analyze_lines_prosody
from src.text_mining import mine_text, kwic
from src.midi_analyzer import analyze_vocal_midi, analyze_backing_midi
from src.writing_brief import generate_writing_brief
from src.reference_profile import build_reference_profile
from src.librettist_report import build_song_genome_summary, generate_librettist_report
from src.providers.mock_cyanite import MockCyanite
from src.providers.factory import get_lyrics_provider, provider_status
from src.contextual_palette.selection_analyzer import classify_selection
from src.contextual_palette.runner import run_all_for_selection, get_available_modules
from src.utils import save_json, save_text, ensure_dir, NumpyEncoder

OUTPUTS_DIR = Path(__file__).parent / "outputs"
TEMP_DIR = Path(__file__).parent / "temp"

st.set_page_config(page_title="MGX Librettist", layout="wide")

PROVIDER_MODE = os.environ.get("PROVIDER_MODE", "mock")

# ─── Session state ──────────────────────────────────────────────────────────
_DEFAULTS = {
    "project_meta": {"title": "", "language": "auto", "created_at": "", "provider_mode": PROVIDER_MODE},
    "mgx_output": None, "mgx_json_str": None, "mgx_report_text": None,
    "cyanite_result": None, "musixmatch_result": None,
    "vocal_midi": None, "backing_midi": None,
    "lyrics_result": None, "mining_result": None, "prosody_result": None,
    "writing_brief": None, "reference_profile": None,
    "palette_results": None, "lyrics_saved": "", "theme_prompt": "",
    "inputs": {"audio_file": "", "vocal_midi_file": "", "backing_midi_file": "",
               "reference_artists": [], "reference_songs": [], "avoid_references": []},
    "R": None, "M": None, "H": None, "X": None, "F": None, "C_data": None,
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _save_upload(uploaded, suffix: str = "") -> str:
    ensure_dir(TEMP_DIR)
    tmp = TEMP_DIR / (suffix + uploaded.name)
    with open(tmp, "wb") as f:
        f.write(uploaded.getbuffer())
    return str(tmp)


def build_full_project() -> dict:
    """Assemble the unified project state JSON."""
    return {
        "project_meta": st.session_state.project_meta,
        "inputs": st.session_state.inputs,
        "analysis": {
            "mgx": st.session_state.mgx_output or {},
            "cyanite": st.session_state.cyanite_result or {},
            "vocal_midi": st.session_state.vocal_midi or {},
            "backing_midi": st.session_state.backing_midi or {},
            "lyrics_structure": st.session_state.lyrics_result or {},
            "lyrics_prosody": st.session_state.prosody_result or {},
            "text_mining": st.session_state.mining_result or {},
            "writing_brief": st.session_state.writing_brief or {},
            "reference_profile": st.session_state.reference_profile or {},
        },
        "writing_studio": {
            "selected_text": (st.session_state.palette_results or {}).get("_selected_text", ""),
            "selection_type": (st.session_state.palette_results or {}).get("_selection_type", ""),
            "palette_outputs": st.session_state.palette_results or {},
        },
        "exports": {
            "mgx_output": "outputs/mgx_output.json",
            "lyrics_mining": "outputs/lyrics_mining.json",
            "full_project": "outputs/full_project.json",
        },
    }


def palette_context() -> dict:
    """Build the rich context passed to palette modules."""
    return {
        "mgx": st.session_state.mgx_output,
        "cyanite": st.session_state.cyanite_result,
        "musixmatch": st.session_state.musixmatch_result,
        "mining": st.session_state.mining_result or {},
        "vocal_midi": st.session_state.vocal_midi or {},
        "lyrics_prosody": st.session_state.prosody_result or {},
        "reference_profile": st.session_state.reference_profile or {},
        "writing_brief": st.session_state.writing_brief or {},
        "bpm": (st.session_state.R or {}).get("bpm"),
    }


# ─── Header ─────────────────────────────────────────────────────────────────
st.title("MGX Librettist")
st.caption("Melody-aware AI lyrics companion for songwriters — local, copyright-safe, mock-by-default.")

_pstatus = provider_status()
if _pstatus["musixmatch"] == "live" or _pstatus["cyanite"] == "live":
    st.success(f"Providers — Musixmatch: **{_pstatus['musixmatch']}** · Cyanite: **{_pstatus['cyanite']}** (mode: {_pstatus['mode']})")
else:
    st.info("No live API keys: using mock providers (Musixmatch / Cyanite). The app is fully usable offline.")

tab_demo, tab_lyrics, tab_refs, tab_studio, tab_export = st.tabs(
    ["1 · Demo Uploader", "2 · Lyrics Prompter", "3 · References", "4 · Writing Studio", "5 · Export"]
)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — DEMO UPLOADER
# ═════════════════════════════════════════════════════════════════════════════
with tab_demo:
    st.header("Demo Uploader")
    st.caption("Upload your demo audio (required). Optionally add vocal/backing MIDI and manual metadata.")

    col_file, col_yt = st.columns(2)
    with col_file:
        uploaded_file = st.file_uploader("Demo audio — WAV / MP3 / FLAC", type=["wav", "mp3", "flac"], key="audio_upload")
    with col_yt:
        yt_url = st.text_input("Or paste a YouTube link", key="yt_url")
        with st.expander("YouTube auth"):
            yt_browser = st.selectbox("Cookies from", ["auto-detect", "chrome", "firefox", "safari", "edge", "brave", "none"], key="yt_browser")
            yt_cookies_file = st.text_input("cookies.txt path", key="yt_cookies_file")

    col_vm, col_bm = st.columns(2)
    with col_vm:
        vocal_midi_up = st.file_uploader("Optional: vocal / topline MIDI", type=["mid", "midi"], key="vocal_midi_up")
    with col_bm:
        backing_midi_up = st.file_uploader("Optional: backing / harmony MIDI", type=["mid", "midi"], key="backing_midi_up")

    with st.expander("Manual metadata (optional)"):
        m1, m2, m3 = st.columns(3)
        meta_title = m1.text_input("Song title", key="meta_title")
        meta_lang = m2.selectbox("Language", ["auto", "en", "it"], key="meta_lang")
        meta_bpm = m3.text_input("Declared BPM", key="meta_bpm")
        m4, m5 = st.columns(2)
        meta_key = m4.text_input("Declared key", key="meta_key")
        meta_notes = m5.text_input("Notes about the song", key="meta_notes")

    run_btn = st.button("Analyze Demo", type="primary", use_container_width=True)

    if run_btn:
        ensure_dir(OUTPUTS_DIR); ensure_dir(TEMP_DIR)
        audio_path = None; source = "file"; yt_title = None; yt_url_used = None; meta_notes_list = []

        if uploaded_file is not None:
            audio_path = _save_upload(uploaded_file)
        elif yt_url and yt_url.strip():
            if not is_valid_youtube_url(yt_url.strip()):
                st.error("Invalid YouTube URL."); st.stop()
            with st.spinner("Downloading from YouTube..."):
                try:
                    _br = yt_browser if yt_browser not in ("auto-detect", "none") else None
                    _ck = yt_cookies_file.strip() or None
                    yt_result = download_audio_from_youtube(yt_url.strip(), output_dir=TEMP_DIR,
                        cookies_from_browser=_br if _br else None, cookies_file=_ck)
                    audio_path = yt_result["audio_path"]; yt_title = yt_result.get("title")
                    yt_url_used = yt_url.strip(); source = "youtube"
                except Exception as e:
                    st.error(f"YouTube download failed: {e}"); st.stop()
        else:
            st.info("Upload a file or paste a URL to continue."); st.stop()

        # Optional MIDI parsing (fails softly)
        if vocal_midi_up is not None:
            vmp = _save_upload(vocal_midi_up, "vocal_")
            st.session_state.vocal_midi = analyze_vocal_midi(vmp)
            st.session_state.inputs["vocal_midi_file"] = vmp
        if backing_midi_up is not None:
            bmp = _save_upload(backing_midi_up, "backing_")
            st.session_state.backing_midi = analyze_backing_midi(bmp)
            st.session_state.inputs["backing_midi_file"] = bmp

        with st.spinner("Loading audio..."): audio_data = load_audio(audio_path)
        with st.spinner("Preprocessing..."): pp = preprocess(audio_data["y"], audio_data["sr"])

        progress = st.progress(0, text="Rhythm...")
        try: R = analyze_rhythm(pp)
        except Exception as e: R = {"error": str(e)}; meta_notes_list.append(str(e))
        progress.progress(20, text="Melody...")
        try: M = analyze_melody(pp)
        except Exception as e: M = {"error": str(e)}; meta_notes_list.append(str(e))
        progress.progress(40, text="Harmony...")
        try: H = analyze_harmony(pp)
        except Exception as e: H = {"error": str(e)}; meta_notes_list.append(str(e))
        progress.progress(55, text="Motifs...")
        try: X = analyze_motif(pp)
        except Exception as e: X = {"error": str(e)}; meta_notes_list.append(str(e))
        progress.progress(70, text="Form...")
        try: F = analyze_form(pp)
        except Exception as e: F = {"error": str(e)}; meta_notes_list.append(str(e))
        progress.progress(80, text="Confidence...")

        if meta_notes:
            meta_notes_list.append(f"User note: {meta_notes}")
        meta = {"source": source, "filename": audio_data["filename"], "youtube_url": yt_url_used,
                "title": meta_title or yt_title, "language": meta_lang,
                "declared_bpm": meta_bpm, "declared_key": meta_key,
                "duration_sec": round(audio_data["duration_sec"], 2),
                "sample_rate": audio_data["original_sr"], "analysis_sample_rate": audio_data["sr"],
                "notes": meta_notes_list}

        _NN = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
        _kc = H.get("key_center", H.get("key", "C"))
        _ki = _NN.index(_kc) if _kc in _NN else 0
        _pc = np.array(M.get("pitch_class_histogram", [0.0]*12))
        _pcr = np.roll(_pc, -_ki); _s = _pcr.sum()
        if _s > 0: _pcr = _pcr / _s
        M["pitch_class_profile_relative"] = _pcr.tolist()

        C_data = compute_confidence(meta, R, M, H, X, F)
        def _strip(d): return {k: v for k, v in d.items() if k != "pass_details"}
        mgx_output = {"meta": meta, "R": _strip(R), "M": _strip(M), "H": _strip(H), "X": _strip(X), "F": _strip(F), "C": C_data}

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
        st.session_state.inputs["audio_file"] = audio_path
        st.session_state.project_meta.update({
            "title": meta_title or yt_title or "",
            "language": meta_lang,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "provider_mode": PROVIDER_MODE,
        })

    # ── Song Genome Summary ──
    if st.session_state.mgx_output:
        mgx = st.session_state.mgx_output
        genome = build_song_genome_summary(mgx, st.session_state.cyanite_result, st.session_state.vocal_midi)
        st.success("Demo analyzed — Song Genome Summary")
        c1, c2, c3, c4 = st.columns(4)
        bpm = genome.get("bpm")
        c1.metric("BPM", f"{bpm:.0f}" if isinstance(bpm, (int, float)) else "?")
        c2.metric("Key", f"{genome.get('key', '?')} {genome.get('mode', '')}")
        oc = genome.get("overall_confidence")
        c3.metric("Confidence", f"{oc:.0%}" if isinstance(oc, (int, float)) else "?")
        c4.metric("Mood (mock)", genome.get("mood", "?") or "?")

        cc1, cc2, cc3 = st.columns(3)
        cc1.caption(f"Time signature: {genome.get('time_signature')}")
        cc2.caption(f"Melodic contour: {genome.get('melodic_contour')}")
        cc3.caption(f"Form: {genome.get('form_sections')}")

        if st.session_state.vocal_midi:
            vm = st.session_state.vocal_midi
            if vm.get("warnings"):
                for w in vm["warnings"]:
                    st.warning(f"Vocal MIDI: {w}")
            else:
                st.caption(f"Vocal MIDI: {vm.get('n_notes')} notes · ~{vm.get('suggested_syllable_slots')} syllable slots · cadence {vm.get('cadence_profile')}")
        else:
            st.caption("No vocal MIDI uploaded: metric fit will use heuristic estimates.")

        with st.expander("Song Genome Summary (JSON)"):
            st.json(genome)
        with st.expander("Full MGX details"):
            st.json(mgx)
        if st.session_state.cyanite_result:
            with st.expander("Cyanite enrichment (mock)"):
                st.json(st.session_state.cyanite_result)
        if st.session_state.backing_midi:
            with st.expander("Backing MIDI analysis"):
                st.json(st.session_state.backing_midi)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 — LYRICS PROMPTER
# ═════════════════════════════════════════════════════════════════════════════
with tab_lyrics:
    st.header("Lyrics Prompter")
    mode = st.radio("Mode", ["A — I already have lyrics", "B — I only have a theme / concept"], key="lyrics_mode")
    lang = st.session_state.project_meta.get("language", "auto")

    if mode.startswith("A"):
        st.caption("Paste your draft lyrics. We analyze structure, prosody, and run text mining.")
        lyrics_text = st.text_area(
            "Your lyrics:", height=300, value=st.session_state.lyrics_saved,
            placeholder="Verse 1\nYour first line here\nSecond line\n\nChorus\nRepeat this line\nRepeat this line",
        )
        if lyrics_text != st.session_state.lyrics_saved:
            st.session_state.lyrics_saved = lyrics_text

        if lyrics_text and lyrics_text.strip():
            lr = analyze_lyrics(lyrics_text)
            st.session_state.lyrics_result = lr
            pr = analyze_lines_prosody(lyrics_text, lang)
            st.session_state.prosody_result = pr

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Lines", lr["n_lines"])
            c2.metric("Stanzas", lr["n_stanzas"])
            c3.metric("Words", lr["n_words"])
            c4.metric("Avg syl/line", pr["average_syllables_per_line"])

            for w in pr.get("warnings", []):
                st.warning(w)

            with st.expander("Per-line prosody"):
                for ln in pr["lines"]:
                    flag = " 🔁" if ln["is_repeated"] else ""
                    st.text(f'  [{ln["estimated_syllables"]:>2} syl] {ln["text"]}{flag}')

            if lr["repeated_lines"]:
                with st.expander(f"Repeated lines ({len(lr['repeated_lines'])})"):
                    for rl in lr["repeated_lines"]:
                        st.text(f'  x{rl["count"]}  "{rl["line"]}"')

            if st.button("Run Text Mining", type="primary"):
                st.session_state.mining_result = mine_text(lyrics_text)

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
    else:
        st.caption("Describe the theme/concept. We generate a Writing Brief (directions, not full lyrics).")
        theme = st.text_area("Theme / concept:", height=150, value=st.session_state.theme_prompt,
            placeholder="e.g. a song about leaving a city at dawn, mixed feelings of relief and loss")
        if theme != st.session_state.theme_prompt:
            st.session_state.theme_prompt = theme

        if st.button("Generate Writing Brief", type="primary"):
            genome = build_song_genome_summary(st.session_state.mgx_output, st.session_state.cyanite_result)
            st.session_state.writing_brief = generate_writing_brief(
                theme, language=lang, mgx_summary=genome, cyanite=st.session_state.cyanite_result)

        wb = st.session_state.writing_brief
        if wb and wb.get("core_theme"):
            st.success(f"Writing Brief — core theme: {wb['core_theme']}")
            st.markdown(f"**Emotional temperature:** {wb['emotional_temperature']}")
            cwa, cwb = st.columns(2)
            with cwa:
                st.markdown("**Promising images**")
                for i in wb["promising_images"]:
                    st.write(f"- {i}")
                st.markdown("**Possible scenes**")
                for s in wb["possible_scenes"]:
                    st.write(f"- {s}")
            with cwb:
                st.markdown("**Title seeds**")
                for t in wb["possible_titles"]:
                    st.write(f"- {t}")
                st.markdown("**Images to avoid (clichés)**")
                for a in wb["images_to_avoid"]:
                    st.write(f"- {a}")
            st.markdown("**Point-of-view options**: " + ", ".join(wb["point_of_view_options"]))
            st.markdown("**Narrative arcs**: " + " · ".join(wb["narrative_arc_options"]))
            st.caption(wb["copyright_safe_note"])


# ═════════════════════════════════════════════════════════════════════════════
# TAB 3 — REFERENCES
# ═════════════════════════════════════════════════════════════════════════════
with tab_refs:
    st.header("References")
    st.caption("Reference Profile — copyright-safe abstraction. We never fetch or display lyrics, only abstract patterns.")

    r1, r2 = st.columns(2)
    ref_artists = r1.text_input("Reference artists (comma separated)", key="ref_artists",
        placeholder="e.g. Joni Mitchell, Leonard Cohen")
    ref_songs = r2.text_input("Reference songs (optional)", key="ref_songs",
        placeholder="e.g. song titles")
    r3, r4 = st.columns(2)
    genre_tags = r3.text_input("Genre / mood tags", key="genre_tags", placeholder="e.g. folk, melancholy")
    avoid_artists = r4.text_input("Avoid sounding like (optional)", key="avoid_artists")

    if st.button("Build Reference Profile", type="primary"):
        artists = [a.strip() for a in ref_artists.split(",") if a.strip()]
        if not artists:
            st.info("No reference artists selected: corpus insights will use generic songwriting patterns.")
        provider, prov_label = get_lyrics_provider()
        seeds = [t.strip() for t in genre_tags.split(",") if t.strip()] or ["love", "night", "city"]
        with st.spinner(f"Querying Musixmatch ({prov_label})..."):
            try:
                profile = build_reference_profile(
                    artists=artists,
                    provider=provider,
                    reference_songs=[s.strip() for s in ref_songs.split(",") if s.strip()],
                    avoid_artists=[a.strip() for a in avoid_artists.split(",") if a.strip()],
                    genre_tags=[t.strip() for t in genre_tags.split(",") if t.strip()],
                    lyrics_context=st.session_state.lyrics_saved,
                )
                themes_snapshot = provider.search_by_theme(seeds)
            except Exception as e:  # network/provider failure → graceful mock fallback
                from src.providers.mock_musixmatch import MockMusixmatch
                st.warning(f"Musixmatch live query failed ({e}); falling back to mock corpus.")
                provider, prov_label = MockMusixmatch(), "mock"
                profile = build_reference_profile(
                    artists=artists, provider=provider,
                    reference_songs=[s.strip() for s in ref_songs.split(",") if s.strip()],
                    avoid_artists=[a.strip() for a in avoid_artists.split(",") if a.strip()],
                    genre_tags=[t.strip() for t in genre_tags.split(",") if t.strip()],
                    lyrics_context=st.session_state.lyrics_saved,
                )
                themes_snapshot = provider.search_by_theme(seeds)
        st.session_state.reference_profile = profile
        st.session_state.inputs["reference_artists"] = artists
        st.session_state.inputs["reference_songs"] = profile["reference_songs"]
        st.session_state.inputs["avoid_references"] = profile["avoid"]
        st.session_state.musixmatch_result = {"themes": themes_snapshot, "source": prov_label}
        st.caption(f"Corpus source: **{prov_label}**")

    profile = st.session_state.reference_profile
    if profile and profile.get("artists") is not None:
        if profile.get("grounded_in_real_catalog"):
            st.success("Reference Profile — copyright-safe abstraction, grounded in the references' real catalog (Musixmatch Analysis)")
        else:
            st.success("Reference Profile — copyright-safe abstraction (generic patterns)")
        ap = profile["abstract_patterns"]
        pc1, pc2 = st.columns(2)
        with pc1:
            st.markdown(f"**Narrative stance:** {ap['narrative_stance']}")
            st.markdown(f"**Imagery density:** {ap['imagery_density']}")
            st.markdown(f"**Verse style:** {ap['verse_style']}")
            st.markdown(f"**Chorus style:** {ap['chorus_style']}")
        with pc2:
            st.markdown("**Common themes:** " + ", ".join(ap["common_themes"]))
            if ap.get("dominant_moods"):
                st.markdown("**Dominant moods (real):** " + ", ".join(ap["dominant_moods"]))
            st.markdown("**Lexical fields:** " + ", ".join(ap["lexical_fields"][:10]))
            st.markdown("**Symbolic register:** " + ", ".join(ap["symbolic_register"]))

        if profile.get("reference_artist_profiles"):
            st.markdown("**Per-artist abstract patterns (from real top tracks)**")
            for prof in profile["reference_artist_profiles"]:
                with st.expander(f"{prof['artist']} — {prof.get('n_tracks_analyzed', 0)} tracks analyzed"):
                    if prof.get("themes"):
                        st.markdown("Themes: " + ", ".join(prof["themes"][:8]))
                    if prof.get("moods"):
                        st.markdown("Moods: " + ", ".join(prof["moods"]))
                    if prof.get("genres"):
                        st.markdown("Genres: " + ", ".join(prof["genres"]))
                    if prof.get("entities"):
                        st.markdown("Entities: " + ", ".join(prof["entities"][:8]))
                    st.caption("Abstract descriptors only — no lyrics.")

        st.markdown("**Creative constraints**")
        for c in profile["creative_constraints"]:
            st.write(f"- {c}")
        st.warning("Safe inspiration rules: " + " · ".join(profile["safe_inspiration_rules"]))
        with st.expander("Reference Profile (JSON)"):
            st.json(profile)


# ═════════════════════════════════════════════════════════════════════════════
# TAB 4 — WRITING STUDIO
# ═════════════════════════════════════════════════════════════════════════════
with tab_studio:
    st.header("Writing Studio")

    # Top summary
    genome = build_song_genome_summary(st.session_state.mgx_output, st.session_state.cyanite_result, st.session_state.vocal_midi)
    s1, s2, s3, s4 = st.columns(4)
    bpm = genome.get("bpm")
    s1.metric("BPM", f"{bpm:.0f}" if isinstance(bpm, (int, float)) else "—")
    s2.metric("Key", f"{genome.get('key', '—')} {genome.get('mode', '')}".strip())
    s3.metric("Mood", genome.get("mood", "—") or "—")
    rp = st.session_state.reference_profile
    s4.metric("References", str(len(rp["artists"])) if rp and rp.get("artists") else "—")

    lyrics_text = st.session_state.lyrics_saved
    if not lyrics_text or not lyrics_text.strip():
        st.warning("No lyrics found. Go to the Lyrics Prompter tab (Mode A) and paste your lyrics.")
    else:
        col_editor, col_palette = st.columns([3, 2])

        with col_editor:
            st.markdown("#### Your lyrics")
            edited = st.text_area("Editable lyrics", value=lyrics_text, height=340, key="studio_lyrics")
            if edited != st.session_state.lyrics_saved:
                st.session_state.lyrics_saved = edited
                lyrics_text = edited
            # line stats
            pr = st.session_state.prosody_result
            if pr:
                with st.expander("Line stats"):
                    for ln in pr["lines"]:
                        st.text(f'  {ln["line_index"]:>2} | {ln["estimated_syllables"]:>2} syl | {ln["text"]}')

            selected_text = st.text_input("Selection (paste a word, phrase, stanza or chorus):",
                key="palette_selection",
                placeholder="e.g. broken heart  |  I walk the empty streets at night")

        with col_palette:
            st.markdown("#### Contextual Palette")
            if selected_text and selected_text.strip():
                sel_type = classify_selection(selected_text, lyrics_text)
                st.caption(f"Detected selection type: **{sel_type.value}**")
                available = get_available_modules(sel_type)
                st.caption(f"{len(available)} tools available: " + ", ".join(m.title for m in available))

                if st.button("Analyze Selection", type="primary", use_container_width=True):
                    st.session_state.palette_results = run_all_for_selection(
                        selected_text, lyrics_text, palette_context())

                res = st.session_state.palette_results
                if res:
                    st.caption(f'Results for: "{res.get("_selected_text", "")[:60]}"')

                    def _show(key, title, icon="•", expanded=False):
                        data = res.get(key)
                        if not data or "error" in data:
                            return None
                        return st.expander(f"{icon} {title}", expanded=expanded), data

                    # Metric Fit
                    out = _show("metric_fit", "Metric Fit", "📏", expanded=True)
                    if out:
                        exp, d = out
                        with exp:
                            st.metric("Fit score", f"{d.get('fit_score', 0):.0%}")
                            st.caption(f"{d.get('estimated_syllables')} syllables vs {d.get('available_melodic_slots')} slots ({d.get('slots_source')})")
                            st.write(d.get("diagnosis", ""))
                            for s in d.get("suggested_adjustments", []):
                                st.info(s)

                    # Stress Alignment
                    out = _show("stress_alignment", "Stress Alignment", "🎯")
                    if out:
                        exp, d = out
                        with exp:
                            st.metric("Alignment", f"{d.get('alignment_score', 0):.0%}")
                            if d.get("strong_words"):
                                st.markdown("**Anchored:** " + " ".join(f"`{w}`" for w in d["strong_words"]))
                            if d.get("weakly_placed_words"):
                                st.markdown("**Weakly placed:** " + " ".join(f"`{w}`" for w in d["weakly_placed_words"]))
                            for s in d.get("suggestions", []):
                                st.caption(s)

                    # Hook Strength
                    out = _show("hook_strength", "Hook Strength", "🪝")
                    if out:
                        exp, d = out
                        with exp:
                            st.metric("Hook score", f"{d.get('hook_score', 0)}/100")
                            for s in d.get("strengths", []):
                                st.success(s)
                            for w in d.get("weaknesses", []):
                                st.warning(w)
                            if d.get("title_candidates"):
                                st.markdown("**Title candidates:** " + ", ".join(d["title_candidates"]))

                    # Singability Check
                    out = _show("singability_check", "Singability Check", "🎤")
                    if out:
                        exp, d = out
                        with exp:
                            st.metric("Singability", f"{d.get('singability_score', 0)}/100")
                            if d.get("difficult_clusters"):
                                st.markdown("**Hard clusters:** " + ", ".join(d["difficult_clusters"]))
                            for w in d.get("fast_note_warnings", []):
                                st.warning(w)
                            for s in d.get("suggestions", []):
                                st.caption(s)

                    # Lexical Constellation
                    out = _show("lexical_constellation", "Lexical Constellation", "🌐")
                    if out:
                        exp, d = out
                        with exp:
                            if d.get("local_connections"):
                                st.markdown("**Local:** " + " ".join(f"`{w}`" for w in d["local_connections"]))
                            if d.get("corpus_connections"):
                                st.markdown("**Corpus:** " + " ".join(f"`{w}`" for w in d["corpus_connections"]))

                    # Rhyme Explorer
                    out = _show("rhyme_explorer", "Rhyme Explorer", "🎵")
                    if out:
                        exp, d = out
                        with exp:
                            for cat in ["perfect_rhymes", "near_rhymes", "assonances", "consonances"]:
                                if d.get(cat):
                                    st.markdown(f"**{cat.replace('_',' ').title()}:** " + " ".join(f"`{w}`" for w in d[cat]))

                    # Metric Rewrite
                    out = _show("metric_rewrite", "Metric-Aware Rewrite", "📐")
                    if out:
                        exp, d = out
                        with exp:
                            om = d.get("original_metrics", {})
                            st.caption(f"Original: {om.get('syllables',0)} syl · target {d.get('target_syllables')}")
                            for alt in d.get("alternatives", []):
                                st.markdown(f"**[{alt['style']}]** {alt['text']}  \n_{alt['estimated_syllables']} syl — {alt['what_changed']} ({alt['fit_note']})_")
                            for w in d.get("warnings", []):
                                st.caption(w)

                    # Emotional Reading
                    out = _show("emotional_reading", "Emotional Reading", "💎")
                    if out:
                        exp, d = out
                        with exp:
                            c1, c2, c3 = st.columns(3)
                            c1.metric("Lyrics", d.get("lyrics_emotion", "?"))
                            c2.metric("Music", d.get("music_emotion", "?"))
                            c3.metric("Alignment", f"{d.get('alignment_score', 0):.0%}")
                            for n in d.get("notes", []):
                                st.info(n)
                            for opt in d.get("creative_options", []):
                                st.caption(f"**{opt['approach']}** — {opt['suggestion']}")

                    # Corpus Insights
                    out = _show("corpus_insights", "Corpus Insights", "📚")
                    if out:
                        exp, d = out
                        with exp:
                            if d.get("common_associations"):
                                st.markdown("**Common:** " + " ".join(f"`{w}`" for w in d["common_associations"]))
                            if d.get("less_common_directions"):
                                st.markdown("**Less explored:** " + " ".join(f"`{w}`" for w in d["less_common_directions"]))
                            for n in d.get("reference_patterns", []):
                                st.caption(n)

                    # Cliche Detector
                    out = _show("cliche_detector", "Cliche Detector", "⚡")
                    if out:
                        exp, d = out
                        with exp:
                            score = d.get("cliche_score", 0)
                            (st.error if score > 70 else st.warning if score > 30 else st.success)(f"Cliche score: {score}/100")
                            for r in d.get("reasons", []):
                                st.caption(r)
                            if d.get("alternatives"):
                                st.markdown("**Try instead:** " + " ".join(f"`{a}`" for a in d["alternatives"]))

                    # Imagery Analyzer
                    ia = res.get("imagery_analyzer")
                    if ia and any(isinstance(v, (int, float)) and v > 0 for v in ia.values()):
                        with st.expander("👁 Imagery Analyzer"):
                            senses = ["visual", "auditory", "tactile", "spatial", "body"]
                            vals = [ia.get(s, 0) for s in senses]
                            if any(v > 0 for v in vals):
                                fig, ax = plt.subplots(figsize=(4, 4), subplot_kw=dict(polar=True))
                                angles = np.linspace(0, 2 * np.pi, len(senses), endpoint=False).tolist()
                                vals_plot = vals + [vals[0]]; angles += [angles[0]]
                                ax.fill(angles, vals_plot, alpha=0.25); ax.plot(angles, vals_plot, linewidth=2)
                                ax.set_xticks(angles[:-1]); ax.set_xticklabels(senses, size=8)
                                ax.set_ylim(0, max(vals_plot) + 0.1)
                                st.pyplot(fig); plt.close()

                    # Narrative Function
                    out = _show("narrative_function", "Narrative Function", "📖")
                    if out:
                        exp, d = out
                        with exp:
                            st.metric("Role", d.get("detected_role", "?"))
                            if d.get("alternatives"):
                                st.caption(f"Alternatives: {', '.join(d['alternatives'])}")

                    # Repetition Radar
                    out = _show("repetition_radar", "Repetition Radar", "🔁")
                    if out:
                        exp, d = out
                        with exp:
                            if d.get("repeated_words"):
                                st.markdown("**Repeated:** " + " ".join(f"`{w['word']}` x{w['count']}" for w in d["repeated_words"][:10]))

                    # Title Finder
                    out = _show("title_finder", "Title Finder", "🏷")
                    if out:
                        exp, d = out
                        with exp:
                            for t in d.get("title_candidates", []):
                                st.markdown(f"**{t['title']}** — _{t['reason']}_")

                    # Inspiration Directions
                    out = _show("inspiration_directions", "Inspiration Directions", "✨", expanded=True)
                    if out:
                        exp, d = out
                        with exp:
                            if d.get("underexplored_territories"):
                                st.markdown("**Underexplored:** " + " ".join(f"`{t}`" for t in d["underexplored_territories"]))
                            for s in d.get("creative_directions", []):
                                st.info(s)
                            for s in d.get("symbolic_opportunities", []):
                                st.caption(s)
                            for p in d.get("creative_prompts", []):
                                st.success(p)
            else:
                st.caption("Paste text from your lyrics into the selection box to activate the palette.")


# ═════════════════════════════════════════════════════════════════════════════
# TAB 5 — EXPORT
# ═════════════════════════════════════════════════════════════════════════════
with tab_export:
    st.header("Export")
    ensure_dir(OUTPUTS_DIR)

    has_mgx = st.session_state.mgx_output is not None
    has_mining = st.session_state.mining_result is not None
    has_palette = st.session_state.palette_results is not None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("MGX", "ready" if has_mgx else "—")
    c2.metric("Text Mining", "ready" if has_mining else "—")
    c3.metric("Reference", "ready" if st.session_state.reference_profile else "—")
    c4.metric("Palette", "ready" if has_palette else "—")

    st.divider()
    full = build_full_project()
    full_json = json.dumps(full, indent=2, cls=NumpyEncoder, ensure_ascii=False)
    report_md = generate_librettist_report(full)

    # persist to disk
    save_json(full, OUTPUTS_DIR / "full_project.json")
    save_text(report_md, OUTPUTS_DIR / "librettist_report.md")
    if has_mining:
        save_json(st.session_state.mining_result, OUTPUTS_DIR / "lyrics_mining.json")

    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button("Download Full Project JSON", full_json,
            file_name="full_project.json", mime="application/json", use_container_width=True)
        if has_mgx:
            st.download_button("MGX JSON", st.session_state.mgx_json_str,
                file_name="mgx_output.json", mime="application/json", use_container_width=True)
    with col_b:
        st.download_button("Librettist Report (Markdown)", report_md,
            file_name="librettist_report.md", mime="text/markdown", use_container_width=True)
        if has_mining:
            st.download_button("Lyrics Mining JSON",
                json.dumps(st.session_state.mining_result, indent=2, ensure_ascii=False),
                file_name="lyrics_mining.json", mime="application/json", use_container_width=True)

    with st.expander("Full project preview"):
        st.json(full)
    with st.expander("Librettist report preview"):
        st.markdown(report_md)

    st.divider()
    st.subheader("Provider debug")
    st.caption("Connectivity checks for external APIs. These do not upload or enqueue any analysis.")

    cyanite_mode = os.environ.get("CYANITE_MODE", "").strip().lower()
    if cyanite_mode != "graphql":
        st.info(
            f"Cyanite is in mock/disabled mode (CYANITE_MODE={cyanite_mode or '(unset)'}). "
            "Set CYANITE_MODE=graphql in .env to enable real GraphQL calls."
        )

    if st.button("Test Cyanite credentials", use_container_width=True):
        with st.spinner("Contacting Cyanite GraphQL..."):
            from src.providers.cyanite import test_cyanite_credentials
            cyanite_test = test_cyanite_credentials()
        st.session_state["cyanite_test_result"] = cyanite_test

    cyanite_test = st.session_state.get("cyanite_test_result")
    if cyanite_test is not None:
        if cyanite_test.get("ok"):
            st.success(cyanite_test.get("message", "Cyanite credentials OK."))
        else:
            st.error(cyanite_test.get("message", "Cyanite test failed."))
        st.caption(f"mode: `{cyanite_test.get('mode')}` · endpoint: `{cyanite_test.get('api_url')}`")
        with st.expander("Raw Cyanite response"):
            st.json(cyanite_test.get("raw") or {"raw": None})

    st.markdown("**Cyanite audio analysis (real)**")
    st.caption("Uploads the audio to Cyanite, runs AudioAnalysisV7 and fetches abstract descriptors. "
               "Does not affect the mock enrichment used in the main flow.")

    _demo_path = st.session_state.get("inputs", {}).get("audio_file")
    cy_upload = st.file_uploader("Audio to analyze (WAV / MP3 / FLAC)", type=["wav", "mp3", "flac"], key="cyanite_audio_up")
    if _demo_path:
        st.caption(f"Or leave empty to use the current demo: `{os.path.basename(_demo_path)}`")

    if cyanite_mode != "graphql":
        st.caption("Enable CYANITE_MODE=graphql to run a real analysis.")
    elif st.button("Run Cyanite analysis (real)", use_container_width=True):
        path_to_analyze = None
        if cy_upload is not None:
            path_to_analyze = _save_upload(cy_upload, "cyanite_")
        elif _demo_path and os.path.exists(_demo_path):
            path_to_analyze = _demo_path
        if not path_to_analyze:
            st.warning("Upload an audio file (or analyze a demo first in Tab 1).")
        else:
            from src.providers.cyanite import analyze_audio_file
            status_box = st.empty()
            with st.spinner("Running Cyanite analysis (this can take a minute)…"):
                cy_real = analyze_audio_file(
                    path_to_analyze,
                    title=st.session_state.get("project_meta", {}).get("title") or None,
                    progress_cb=lambda m: status_box.info(m),
                )
            status_box.empty()
            st.session_state["cyanite_real_result"] = cy_real

    cy_real = st.session_state.get("cyanite_real_result")
    if cy_real is not None:
        if cy_real.get("ok"):
            st.success(cy_real.get("message", "Analysis finished."))
            st.caption(f"track id: `{cy_real.get('track_id')}` · status: `{cy_real.get('status')}`")
            st.json(cy_real.get("analysis") or {})
            with st.expander("Raw Cyanite analysis response"):
                st.json(cy_real.get("raw") or {})
        else:
            st.error(cy_real.get("message", "Analysis failed."))
            if cy_real.get("track_id"):
                st.caption(f"track id: `{cy_real.get('track_id')}` · status: `{cy_real.get('status')}`")
