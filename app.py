"""MGX Librettist — melody-aware AI lyrics companion for songwriters."""
from __future__ import annotations

import json
import os
import re
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
from src.contextual_palette.llm_provider import get_llm_provider, llm_status
from src.contextual_palette.audit import build_selection_audit
from src.contextual_palette.rephrase_selection import rephrase_selection
from src.draft_composer import (
    build_composition_brief, compose_draft, draft_to_text, line_syllable_targets,
    regenerate_section,
)
from src.utils import save_json, save_text, ensure_dir, NumpyEncoder

OUTPUTS_DIR = Path(__file__).parent / "outputs"
TEMP_DIR = Path(__file__).parent / "temp"

st.set_page_config(page_title="MGX Librettist", layout="wide")

PROVIDER_MODE = os.environ.get("PROVIDER_MODE", "mock")

# ─── Session state ──────────────────────────────────────────────────────────
_DEFAULTS = {
    "project_meta": {"title": "", "language": "auto", "created_at": "", "provider_mode": PROVIDER_MODE},
    "mgx_output": None, "mgx_json_str": None, "mgx_report_text": None,
    "cyanite_result": None, "cyanite_source": None, "cyanite_raw": None,
    "musixmatch_result": None, "musixmatch_last_call": None,
    "vocal_midi": None, "backing_midi": None,
    "lyrics_result": None, "mining_result": None, "prosody_result": None,
    "writing_brief": None, "reference_profile": None,
    "generated_draft": None, "composition_brief": None,
    "palette_results": None, "lyrics_saved": "", "theme_prompt": "",
    "selected_text": "", "selection_type": "", "selection_line_range": None,
    "selection_audit": None, "rephrase_candidate": None, "apply_confirm": "",
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


def run_cyanite_enrichment(audio_path: str | None, title: str | None = None, progress_cb=None):
    """Run Cyanite enrichment for the main flow with graceful fallback.

    Returns (descriptors: dict, source: str, raw: dict | None) where source is
    one of: "cyanite_live", "cyanite_mock_fallback", "cyanite_mock".
    """
    def _mock(reason: str | None = None):
        mock = MockCyanite()
        data = mock.analyze_audio(audio_path or "mock")
        data["tags"] = mock.similarity_tags(audio_path or "mock")
        if reason:
            data["_fallback_reason"] = reason
        return data

    mode = os.environ.get("CYANITE_MODE", "").strip().lower()
    has_key = bool(os.environ.get("CYANITE_API_KEY", "").strip())

    if mode == "graphql" and has_key and audio_path:
        try:
            from src.providers.cyanite import analyze_audio_file
            out = analyze_audio_file(audio_path, title=title, progress_cb=progress_cb)
            if out.get("ok") and out.get("analysis"):
                return out["analysis"], "cyanite_live", out.get("raw")
            return _mock(out.get("message")), "cyanite_mock_fallback", None
        except Exception as exc:  # noqa: BLE001 - never break the main flow
            return _mock(str(exc)), "cyanite_mock_fallback", None

    return _mock(), "cyanite_mock"


def build_full_project() -> dict:
    """Assemble the unified project state JSON."""
    genome = build_song_genome_summary(
        st.session_state.mgx_output, st.session_state.cyanite_result,
        st.session_state.vocal_midi, st.session_state.cyanite_source,
    ) if st.session_state.mgx_output else {}
    return {
        "project_meta": st.session_state.project_meta,
        "inputs": st.session_state.inputs,
        "analysis": {
            "mgx": st.session_state.mgx_output or {},
            "cyanite": st.session_state.cyanite_result or {},
            "cyanite_source": st.session_state.cyanite_source,
            "song_genome_summary": genome,
            "vocal_midi": st.session_state.vocal_midi or {},
            "backing_midi": st.session_state.backing_midi or {},
            "lyrics_structure": st.session_state.lyrics_result or {},
            "lyrics_prosody": st.session_state.prosody_result or {},
            "text_mining": st.session_state.mining_result or {},
            "writing_brief": st.session_state.writing_brief or {},
            "reference_profile": st.session_state.reference_profile or {},
            "generated_draft": st.session_state.generated_draft or {},
            "composition_brief": st.session_state.composition_brief or {},
        },
        "writing_studio": {
            "selected_text": st.session_state.selected_text or "",
            "selection_type": st.session_state.selection_type or "",
            "selection_line_range": st.session_state.selection_line_range,
            "selection_audit": st.session_state.selection_audit or {},
            "copyright_safe": True,
            "stored_content_policy": "abstract_descriptors_only_no_lyrics",
        },
        "exports": {
            "mgx_output": "outputs/mgx_output.json",
            "lyrics_mining": "outputs/lyrics_mining.json",
            "full_project": "outputs/full_project.json",
        },
    }


def palette_context() -> dict:
    """Build the rich context passed to palette modules."""
    genome = build_song_genome_summary(
        st.session_state.mgx_output, st.session_state.cyanite_result,
        st.session_state.vocal_midi, st.session_state.cyanite_source,
    ) if st.session_state.mgx_output else {}
    return {
        "song_genome_summary": genome,
        "mgx": st.session_state.mgx_output,
        "cyanite": st.session_state.cyanite_result,
        "musixmatch": st.session_state.musixmatch_result,
        "mining": st.session_state.mining_result or {},
        "vocal_midi": st.session_state.vocal_midi or {},
        "backing_midi": st.session_state.backing_midi or {},
        "lyrics_prosody": st.session_state.prosody_result or {},
        "reference_profile": st.session_state.reference_profile or {},
        "writing_brief": st.session_state.writing_brief or {},
        "bpm": (st.session_state.R or {}).get("bpm"),
    }


def _segment_lyrics(text: str):
    """Split lyrics into selectable lines and stanzas (click-to-select model).

    Returns (raw_lines, lines, stanzas):
    - raw_lines: original ``text.splitlines()`` (used for index-safe replacement)
    - lines: [{idx, text, is_header, chorus}] for each non-empty line
    - stanzas: [{start, end, kind, text, line_idxs}] grouping contiguous lines
    """
    raw_lines = text.splitlines()
    lines: list[dict] = []
    stanzas: list[dict] = []
    cur: list[dict] = []
    cur_chorus = False

    def _flush():
        nonlocal cur, cur_chorus
        idxs = [c["idx"] for c in cur if not c["is_header"]]
        if idxs:
            stanzas.append({
                "start": idxs[0], "end": idxs[-1],
                "kind": "CHORUS" if cur_chorus else "STANZA",
                "text": "\n".join(raw_lines[i] for i in idxs),
                "line_idxs": idxs,
            })
        cur = []
        cur_chorus = False

    for i, ln in enumerate(raw_lines):
        s = ln.strip()
        if not s:
            _flush()
            continue
        is_header = bool(re.match(r"^[\[#]", s))
        if is_header and re.search(r"chorus|ritornello|hook|refrain", s, re.I):
            cur_chorus = True
        rec = {"idx": i, "text": ln, "is_header": is_header,
               "chorus": cur_chorus and not is_header}
        lines.append(rec)
        cur.append(rec)
    _flush()
    return raw_lines, lines, stanzas


# ─── Header ─────────────────────────────────────────────────────────────────
_LOGO_PATH = Path(__file__).parent / "images" / "librettist-logo.webp"
if _LOGO_PATH.exists():
    st.image(str(_LOGO_PATH), width=320)
else:
    st.title("MGX Librettist")
st.caption("Melody-aware AI lyrics companion for songwriters — local, copyright-safe, mock-by-default.")

_pstatus = provider_status()
if _pstatus["musixmatch"] == "live" or _pstatus["cyanite"] == "live":
    st.success(f"Providers — Musixmatch: **{_pstatus['musixmatch']}** · Cyanite: **{_pstatus['cyanite']}** (mode: {_pstatus['mode']})")
else:
    st.info("No live API keys: using mock providers (Musixmatch / Cyanite). The app is fully usable offline.")

def _tab_label(base: str, done: bool) -> str:
    return f"{base} ✅" if done else base


_demo_done = bool(st.session_state.mgx_output)
_lyrics_done = bool(st.session_state.mining_result) or bool(
    st.session_state.writing_brief and st.session_state.writing_brief.get("core_theme")
)
_refs_done = bool(st.session_state.reference_profile and st.session_state.reference_profile.get("artists"))
_studio_done = bool((st.session_state.lyrics_saved or "").strip()) or bool(st.session_state.generated_draft)

tab_demo, tab_lyrics, tab_refs, tab_studio, tab_export = st.tabs([
    _tab_label("1 · Demo Uploader", _demo_done),
    _tab_label("2 · Lyrics Prompter", _lyrics_done),
    _tab_label("3 · References", _refs_done),
    _tab_label("4 · Writing Studio", _studio_done),
    "5 · Export",
])


# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 — DEMO UPLOADER
# ═════════════════════════════════════════════════════════════════════════════
with tab_demo:
    st.header("Demo Uploader")
    st.caption("Upload your demo audio (required). Optionally add vocal/backing MIDI and manual metadata.")

    uploaded_file = st.file_uploader("Demo audio — WAV / MP3 / FLAC", type=["wav", "mp3", "flac"], key="audio_upload")

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
        audio_path = None; source = "file"; meta_notes_list = []

        if uploaded_file is not None:
            audio_path = _save_upload(uploaded_file)
        else:
            st.info("Upload an audio file (WAV / MP3 / FLAC) to continue."); st.stop()

        # Optional MIDI parsing (fails softly — never crash the analysis)
        if vocal_midi_up is not None:
            try:
                vmp = _save_upload(vocal_midi_up, "vocal_")
                st.session_state.vocal_midi = analyze_vocal_midi(vmp)
                st.session_state.inputs["vocal_midi_file"] = vmp
            except Exception as e:  # noqa: BLE001
                st.session_state.vocal_midi = {"n_notes": 0, "warnings": [f"Could not process vocal MIDI: {e}"]}
                st.warning(f"Vocal MIDI could not be processed: {e}. Continuing in heuristic mode.")
        if backing_midi_up is not None:
            try:
                bmp = _save_upload(backing_midi_up, "backing_")
                st.session_state.backing_midi = analyze_backing_midi(bmp)
                st.session_state.inputs["backing_midi_file"] = bmp
            except Exception as e:  # noqa: BLE001
                st.session_state.backing_midi = {"warnings": [f"Could not process backing MIDI: {e}"]}
                st.warning(f"Backing MIDI could not be processed: {e}. Continuing without it.")

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
        meta = {"source": source, "filename": audio_data["filename"],
                "title": meta_title, "language": meta_lang,
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

        progress.progress(90, text="Cyanite enrichment...")
        cy_data, cy_source, cy_raw = run_cyanite_enrichment(
            audio_path, title=meta_title or None,
            progress_cb=lambda m: progress.progress(92, text=f"Cyanite: {m}"),
        )

        progress.progress(100, text="Done!")
        save_json(mgx_output, OUTPUTS_DIR / "mgx_output.json")
        report_text = generate_report(mgx_output)
        save_text(report_text, OUTPUTS_DIR / "mgx_report.md")

        st.session_state.mgx_output = mgx_output
        st.session_state.mgx_json_str = json.dumps(mgx_output, indent=2, cls=NumpyEncoder, ensure_ascii=False)
        st.session_state.mgx_report_text = report_text
        st.session_state.cyanite_result = cy_data
        st.session_state.cyanite_source = cy_source
        st.session_state.cyanite_raw = cy_raw
        st.session_state.R = R; st.session_state.M = M; st.session_state.H = H
        st.session_state.X = X; st.session_state.F = F; st.session_state.C_data = C_data
        st.session_state.inputs["audio_file"] = audio_path
        st.session_state.project_meta.update({
            "title": meta_title or "",
            "language": meta_lang,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "provider_mode": PROVIDER_MODE,
        })

    # ── Song Genome Summary ──
    if st.session_state.mgx_output:
        mgx = st.session_state.mgx_output
        cy_source = st.session_state.cyanite_source
        genome = build_song_genome_summary(mgx, st.session_state.cyanite_result,
                                           st.session_state.vocal_midi, cy_source)
        st.success("Demo analyzed — Song Genome Summary")

        _cy_badge = {
            "cyanite_live": "Cyanite: live",
            "cyanite_mock_fallback": "Cyanite: mock (live failed)",
            "cyanite_mock": "Cyanite: mock",
        }.get(cy_source, "Cyanite: mock")
        if cy_source == "cyanite_live":
            st.caption(f":green[{_cy_badge}]")
        elif cy_source == "cyanite_mock_fallback":
            reason = (st.session_state.cyanite_result or {}).get("_fallback_reason", "unknown error")
            st.warning(f"Cyanite live analysis failed — using mock data. Reason: {reason}")
        else:
            st.caption(_cy_badge)

        c1, c2, c3, c4 = st.columns(4)
        bpm = genome.get("bpm")
        c1.metric("BPM", f"{bpm:.0f}" if isinstance(bpm, (int, float)) else "?")
        c2.metric("Key", genome.get("key_sources", {}).get("chosen") or "?")
        oc = genome.get("overall_confidence")
        c3.metric("Confidence", f"{oc:.0%}" if isinstance(oc, (int, float)) else "?")
        c4.metric("Mood", genome.get("mood") or "?")

        # MGX vs Cyanite vs chosen
        bs = genome.get("bpm_sources", {}); ks = genome.get("key_sources", {})
        d1, d2 = st.columns(2)
        d1.caption(f"**BPM** — MGX: {bs.get('mgx')} · Cyanite: {bs.get('cyanite')} · chosen: {bs.get('chosen')}")
        d2.caption(f"**Key** — MGX: {ks.get('mgx')} · Cyanite: {ks.get('cyanite')} · chosen: {ks.get('chosen')}")

        e1, e2, e3, e4 = st.columns(4)
        e1.caption(f"Energy: {genome.get('energy')}")
        e2.caption(f"Valence: {genome.get('valence')}")
        e3.caption(f"Arousal: {genome.get('arousal')}")
        e4.caption(f"Time signature: {genome.get('time_signature')}")

        g1, g2 = st.columns(2)
        _genres = genome.get("genres") or []
        _subs = genome.get("subgenres") or []
        g1.caption(f"Genre: {', '.join(_genres) if _genres else genome.get('genre') or '—'}"
                   + (f" · subgenre: {', '.join(_subs)}" if _subs else ""))
        _instr = genome.get("instrumentation") or []
        g2.caption(f"Instrumentation: {', '.join(_instr) if _instr else '—'}")

        f1, f2 = st.columns(2)
        f1.caption(f"Melodic contour: {genome.get('melodic_contour')}")
        f2.caption(f"Form: {genome.get('form_sections')}")
        if genome.get("cyanite_caption"):
            st.caption(f"Cyanite caption: _{genome.get('cyanite_caption')}_")

        for w in genome.get("warnings", []) or []:
            st.caption(f":orange[⚠ {w}]")

        vm = st.session_state.vocal_midi
        if vm and vm.get("n_notes"):
            st.markdown("#### 🎙 Vocal Melody Map")
            mr = vm.get("melodic_range") or {}
            n_phrases = len(vm.get("phrase_estimates") or [])
            v1, v2, v3, v4 = st.columns(4)
            v1.metric("Notes", vm.get("n_notes", 0))
            v2.metric("Duration", f"{vm.get('duration_sec', 0):.1f}s")
            _rng = mr.get("range_semitones")
            v3.metric("Melodic range", f"{_rng} st" if _rng is not None else "—")
            v4.metric("Phrases", n_phrases)
            w1, w2, w3, w4 = st.columns(4)
            w1.caption(f"Avg note duration: {vm.get('average_note_duration', 0):.2f}s")
            w2.caption(f"Suggested syllable slots: {vm.get('suggested_syllable_slots', 0)}")
            w3.caption(f"Strong positions: {len(vm.get('strong_positions') or [])}")
            w4.caption(f"Cadence: {vm.get('cadence_profile') or '—'}")
            if mr.get("min_pitch_name") and mr.get("max_pitch_name"):
                st.caption(f"Range: {mr['min_pitch_name']} → {mr['max_pitch_name']}")
            _phrases = vm.get("phrase_estimates") or []
            if _phrases:
                _slots = [int(p.get("syllable_slots", 0)) for p in _phrases]
                st.caption(f"**Per-phrase syllable slots (notes → slots):** {_slots} "
                           "— these become the per-line syllable targets sent to the AI.")
                with st.expander("Phrase breakdown (note → slot mapping)"):
                    for p in _phrases:
                        st.text(
                            f"  Phrase {p.get('index', 0) + 1}: "
                            f"{p.get('n_notes', 0)} notes → {p.get('syllable_slots', 0)} syllable slots "
                            f"(t={p.get('start', 0):.1f}s–{p.get('end', 0):.1f}s)"
                        )
            for w in vm.get("warnings", []) or []:
                st.warning(f"Vocal MIDI: {w}")
            st.caption(":green[Metric Fit and Stress Alignment will run in melody-aware mode.]")
        else:
            if vm and vm.get("warnings"):
                for w in vm["warnings"]:
                    st.warning(f"Vocal MIDI: {w}")
            st.info("No vocal MIDI uploaded: Metric Fit and Stress Alignment will use heuristic mode.")

        with st.expander("Song Genome Summary (JSON)"):
            st.json(genome)
        with st.expander("Full MGX details"):
            st.json(mgx)
        if st.session_state.cyanite_result:
            with st.expander(f"Cyanite descriptors ({cy_source or 'mock'})"):
                st.json(st.session_state.cyanite_result)
        if st.session_state.cyanite_raw:
            with st.expander("Cyanite raw GraphQL response (debug)"):
                st.json(st.session_state.cyanite_raw)
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
                # Confirm the abstract signals that will feed the AI Draft Composer.
                from src.draft_composer import _mining_signals
                _sig = _mining_signals(mr)
                _ok = bool(_sig.get("top_words"))
                (st.caption if _ok else st.warning)(
                    (":green[✓ Signals ready for the AI Draft Composer]" if _ok
                     else ":orange[Not enough text for strong signals]")
                    + f" — top words: {', '.join(_sig.get('top_words', [])[:6]) or '—'}"
                    + (f" · bigrams: {', '.join(_sig.get('top_bigrams', [])[:4])}" if _sig.get("top_bigrams") else "")
                )
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

        _llm_b = llm_status()
        if _llm_b["status"] == "live":
            st.caption(f":green[Writing Brief will be AI-generated from your prompt ({_llm_b['provider']} · {_llm_b['model']}).]")
        else:
            st.caption(f":orange[LLM mock ({_llm_b.get('reason') or 'not configured'}) — Writing Brief uses a heuristic template.]")

        if st.button("Generate Writing Brief", type="primary"):
            genome = build_song_genome_summary(st.session_state.mgx_output, st.session_state.cyanite_result)
            with st.spinner("Building your writing brief..."):
                st.session_state.writing_brief = generate_writing_brief(
                    theme, language=lang, mgx_summary=genome,
                    cyanite=st.session_state.cyanite_result,
                    provider=get_llm_provider(),
                    reference_profile=st.session_state.reference_profile,
                )

        wb = st.session_state.writing_brief
        if wb and wb.get("core_theme"):
            _src = wb.get("source")
            if _src == "ai":
                st.success(f"Writing Brief (AI-generated) — core theme: {wb['core_theme']}")
            else:
                st.success(f"Writing Brief (heuristic template) — core theme: {wb['core_theme']}")
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

    # ── Musixmatch provider status box ──
    _ps = provider_status()
    _mm = _ps.get("musixmatch")
    _last = st.session_state.get("musixmatch_last_call")
    with st.container(border=True):
        st.markdown("**Musixmatch provider status**")
        sb1, sb2, sb3 = st.columns(3)
        sb1.caption(f"Provider mode: `{_ps.get('mode')}`")
        if _mm == "live":
            sb2.caption(":green[Musixmatch: live (API key present)]")
        else:
            _has_key = bool(os.environ.get("MUSIXMATCH_API_KEY", "").strip())
            sb2.caption(":orange[Musixmatch: mock]" + ("" if _has_key else " · missing API key"))
        if _last:
            _ok = _last.get("ok")
            sb3.caption((":green[" if _ok else ":red[") + f"Last call: {_last.get('status')}]")
        else:
            sb3.caption("Last call: —")
        st.caption(":blue[Abstract descriptors only — no lyrics stored.]")

    with st.expander("💡 Suggested references demo"):
        st.markdown(
            "1. Add 2–3 reference artists (e.g. *Joni Mitchell, Leonard Cohen*).\n"
            "2. Click **Build Reference Profile**.\n"
            "3. Go to the **Writing Studio** tab.\n"
            "4. Select a stanza from your lyrics.\n"
            "5. Run **Corpus Insights** or **Inspiration Directions** — they will use this profile."
        )

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
        _kwargs = dict(
            reference_songs=[s.strip() for s in ref_songs.split(",") if s.strip()],
            avoid_artists=[a.strip() for a in avoid_artists.split(",") if a.strip()],
            genre_tags=[t.strip() for t in genre_tags.split(",") if t.strip()],
            lyrics_context=st.session_state.lyrics_saved,
        )
        provider_st = provider_status()
        fallback_reason = None
        with st.spinner(f"Querying Musixmatch ({prov_label})..."):
            try:
                source = "musixmatch_live" if prov_label == "musixmatch" else "musixmatch_mock"
                profile = build_reference_profile(
                    artists=artists, provider=provider, source=source,
                    provider_status=provider_st, **_kwargs,
                )
                themes_snapshot = provider.search_by_theme(seeds)
                call_status = "ok"
            except Exception as e:  # network/provider failure → graceful mock fallback
                from src.providers.mock_musixmatch import MockMusixmatch
                fallback_reason = str(e)
                st.warning(f"Musixmatch live query failed ({e}); falling back to mock corpus.")
                provider, prov_label = MockMusixmatch(), "mock"
                profile = build_reference_profile(
                    artists=artists, provider=provider,
                    source="musixmatch_mock_fallback", provider_status=provider_st,
                    fallback_reason=fallback_reason, **_kwargs,
                )
                themes_snapshot = provider.search_by_theme(seeds)
                call_status = f"fallback: {fallback_reason[:80]}"
        st.session_state.reference_profile = profile
        st.session_state.inputs["reference_artists"] = artists
        st.session_state.inputs["reference_songs"] = profile["reference_songs"]
        st.session_state.inputs["avoid_references"] = profile["avoid"]
        st.session_state.musixmatch_result = {"themes": themes_snapshot, "source": prov_label}
        st.session_state.musixmatch_last_call = {
            "ok": fallback_reason is None,
            "status": call_status,
            "source": profile.get("source"),
            "n_artists_analyzed": len(profile.get("reference_artist_profiles", [])),
        }

    profile = st.session_state.reference_profile
    if profile and profile.get("artists") is not None:
        st.markdown("### Reference Profile — copyright-safe abstraction")
        _src = profile.get("source")
        if _src == "musixmatch_live":
            st.success("✅ Grounded in Musixmatch API")
        elif _src == "musixmatch_mock_fallback":
            st.warning(f"Using mock fallback because: {profile.get('fallback_reason') or 'live query failed'}")
        else:
            st.info("Using mock corpus profile (Musixmatch not live)")

        ap = profile["abstract_patterns"]
        st.caption(f"**Artists analyzed:** {', '.join(profile.get('artists') or []) or '—'}  ·  "
                   f"**Source:** `{_src}`")

        pc1, pc2 = st.columns(2)
        with pc1:
            st.markdown("**Common themes:** " + (", ".join(ap["common_themes"]) or "—"))
            if ap.get("dominant_moods"):
                st.markdown("**Dominant moods:** " + ", ".join(ap["dominant_moods"]))
            if ap.get("genres"):
                st.markdown("**Genres / stylistic territories:** " + ", ".join(ap["genres"]))
            st.markdown("**Entities / symbolic territories:** " + (", ".join(ap["symbolic_register"]) or "—"))
        with pc2:
            st.markdown(f"**Narrative stance:** {ap['narrative_stance'] or '—'}")
            st.markdown(f"**Imagery density:** {ap['imagery_density'] or '—'}")
            st.markdown(f"**Verse tendencies:** {ap['verse_style'] or '—'}")
            st.markdown(f"**Chorus tendencies:** {ap['chorus_style'] or '—'}")
            st.markdown("**Lexical fields:** " + (", ".join(ap["lexical_fields"][:10]) or "—"))

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
        if profile.get("avoid"):
            st.markdown("**Avoid / overused territories**")
            for a in profile["avoid"]:
                st.write(f"- {a}")
        st.warning("Safe inspiration rules: " + " · ".join(profile["safe_inspiration_rules"]))
        st.caption(f"copyright_safe: {profile.get('copyright_safe')} · policy: {profile.get('stored_content_policy')}")

        with st.expander("Provider debug (sanitized — no lyrics/quotes)"):
            from src.reference_profile import strip_literal_text
            st.caption("Any literal-text fields are stripped before display/export.")
            st.json(strip_literal_text({
                "source": profile.get("source"),
                "provider_status": profile.get("provider_status"),
                "last_call": st.session_state.get("musixmatch_last_call"),
                "themes_snapshot": (st.session_state.get("musixmatch_result") or {}).get("themes"),
            }))
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

    _melody_aware = bool(st.session_state.vocal_midi and st.session_state.vocal_midi.get("n_notes"))
    with st.expander("💡 How the Writing Studio works", expanded=not st.session_state.selected_text):
        st.markdown(
            "1. **Click a line or a block** in the lyrics editor on the left.\n"
            "2. The right panel **audits it automatically** — why it works or doesn't.\n"
            "3. Set **mood**, **rhyme structure** and an optional **reference artist**.\n"
            "4. Click **Rephrase** for a melody-aware alternative (OpenAI runs only on click).\n"
            "5. Click **Apply** to replace just that line/block in your draft."
        )
        if _melody_aware:
            st.caption(":green[Vocal MIDI detected — Metric Fit & Stress Alignment run in melody-aware mode.]")
        else:
            st.caption(":orange[No vocal MIDI — melody-aware tools run in heuristic mode. Upload a vocal MIDI in Tab 1 for melody-aware analysis.]")

    # Reference context summary (Musixmatch) — visible so judges see it is active.
    with st.container(border=True):
        if rp and rp.get("artists"):
            _rsrc = rp.get("source")
            _badge = {
                "musixmatch_live": ":green[Musixmatch live]",
                "musixmatch_mock_fallback": ":orange[mock fallback]",
                "musixmatch_mock": ":grey[mock]",
            }.get(_rsrc, ":grey[mock]")
            _rap = rp.get("abstract_patterns", {})
            st.caption(
                f"**Reference profile:** available · **Source:** {_badge} · "
                f"**Artists:** {', '.join(rp['artists'])}"
            )
            _tops = (_rap.get("common_themes") or [])[:4]
            _moods = (_rap.get("dominant_moods") or [])[:4]
            if _tops or _moods:
                st.caption(
                    "Top themes: " + (", ".join(_tops) or "—")
                    + "  ·  Moods: " + (", ".join(_moods) or "—")
                )
            st.caption(":blue[Corpus Insights & Inspiration Directions will use this reference profile.]")
        else:
            st.caption("**Reference profile:** missing — add reference artists in the **References** tab to ground suggestions.")

    # Metric Draft Scaffold is rendered below the reactive editor (Select → Audit
    # → Rephrase → Apply is the primary interaction).

    lyrics_text = st.session_state.lyrics_saved or ""
    if not lyrics_text.strip():
        st.info("No lyrics yet — use **🎼 Metric Draft Scaffold** below to draft on the melody, "
                "or paste your own in **Lyrics Prompter → Mode A**. "
                "Then click any line or block here to audit and rephrase it.")
    else:
        col_editor, col_palette = st.columns([3, 2])

        with col_editor:
            st.markdown("#### Lyrics editor")
            edited = st.text_area("Edit freely — then click a line/block below to audit it",
                                  value=lyrics_text, height=240, key="studio_lyrics")
            if edited != st.session_state.lyrics_saved:
                st.session_state.lyrics_saved = edited
                lyrics_text = edited

            _raw_lines, _seg_lines, _stanzas = _segment_lyrics(lyrics_text)
            st.caption("Click **Select block** for a stanza/chorus, or a single line to audit just that line.")
            for _si, _stz in enumerate(_stanzas):
                with st.container(border=True):
                    _hc1, _hc2 = st.columns([3, 1])
                    _block_selected = st.session_state.selection_line_range == [_stz["start"], _stz["end"]]
                    _hc1.caption(("✅ " if _block_selected else "") +
                                 f"**{_stz['kind']}** · lines {_stz['start']+1}–{_stz['end']+1}")
                    if _hc2.button("Select block", key=f"selstz_{_si}"):
                        st.session_state.selected_text = _stz["text"]
                        st.session_state.selection_type = _stz["kind"]
                        st.session_state.selection_line_range = [_stz["start"], _stz["end"]]
                        st.session_state.rephrase_candidate = None
                        st.rerun()
                    for _li in _stz["line_idxs"]:
                        _ltext = _raw_lines[_li]
                        if re.match(r"^[\[#]", _ltext.strip()):
                            st.caption(_ltext)
                            continue
                        _lbl = _ltext.strip()[:50] or "(blank)"
                        _is_sel = st.session_state.selection_line_range == [_li, _li]
                        if st.button(("● " if _is_sel else "○ ") + _lbl, key=f"selln_{_li}",
                                     use_container_width=True):
                            st.session_state.selected_text = _ltext
                            st.session_state.selection_type = "CHORUS" if _stz["kind"] == "CHORUS" else "LINE"
                            st.session_state.selection_line_range = [_li, _li]
                            st.session_state.rephrase_candidate = None
                            st.rerun()

            _pr = st.session_state.prosody_result
            if _pr:
                with st.expander("Line stats (syllables)"):
                    for ln in _pr["lines"]:
                        st.text(f'  {ln["line_index"]:>2} | {ln["estimated_syllables"]:>2} syl | {ln["text"]}')

        with col_palette:
            st.markdown("#### Line / Block Audit")
            if st.session_state.apply_confirm:
                st.success(st.session_state.apply_confirm)
                st.session_state.apply_confirm = ""
            _sel = (st.session_state.selected_text or "").strip()
            if not _sel:
                st.info("Select a line or block in the lyrics editor to audit it.")
                st.session_state.selection_audit = None
            else:
                _ctx = palette_context()
                _ctx["full_lyrics"] = lyrics_text
                _ctx["selection_type"] = st.session_state.selection_type
                _audit = build_selection_audit(st.session_state.selected_text, _ctx)
                st.session_state.selection_audit = _audit

                st.caption(f'Selected · **{_audit.get("selection_type", "?")}** · "{_sel[:70]}"')
                st.markdown(f"**Why this works / doesn't:** {_audit.get('summary_blurb', '')}")

                _scores = _audit.get("scores", {})
                for _k, _lab in [
                    ("metric_fit", "Metric Fit"), ("stress_alignment", "Stress Alignment"),
                    ("singability", "Singability"), ("mood_alignment", "Mood Alignment"),
                    ("rhyme_structure", "Rhyme Structure"), ("imagery_strength", "Imagery Strength"),
                ]:
                    _v = _scores.get(_k)
                    if _v is None:
                        continue
                    st.progress(min(100, max(0, int(_v))) / 100, text=f"{_lab}: {int(_v)}/100")
                _cr = int(_scores.get("cliche_risk", 0))
                st.progress(_cr / 100, text=f"Cliché Risk: {_cr}/100 (lower is better)")

                _refblock = _audit.get("reference", {})
                _rscore = _refblock.get("score")
                if _rscore is not None:
                    st.progress(min(100, max(0, int(_rscore))) / 100,
                                text=f"Reference Alignment: {int(_rscore)}/100")

                _m = _audit.get("metric", {})
                if _m.get("target_syllable_range"):
                    _tr = _m["target_syllable_range"]
                    st.caption(f":blue[Metric ({_m.get('mode', 'heuristic')}): "
                               f"~{_m.get('estimated_syllables')} syllables · target {_tr[0]}–{_tr[1]}]")

                _diag = _audit.get("diagnosis", {})
                with st.expander("Diagnosis & suggested action", expanded=True):
                    for _x in _diag.get("what_works", []):
                        st.caption(f"✅ {_x}")
                    for _x in _diag.get("what_does_not_work", []):
                        st.caption(f"⚠️ {_x}")
                    for _a in _diag.get("recommended_action", []):
                        st.info(_a)

                _refsrc = _refblock.get("source", "none")
                _refbadge = {
                    "musixmatch_live": ":green[Musixmatch live]",
                    "musixmatch_mock_fallback": ":orange[mock fallback]",
                    "musixmatch_mock": ":grey[mock]",
                    "none": ":grey[no reference profile]",
                }.get(_refsrc, ":grey[mock]")
                st.caption(f"Reference: {_refbadge}"
                           + (f" · themes: {', '.join(_refblock.get('related_themes', [])[:4])}"
                              if _refblock.get("related_themes") else ""))

                st.markdown("---")
                st.markdown("##### Rephrase this selection")

                _mood_opts = ["darker / more introspective", "balanced", "brighter / more uplifting"]
                _gmood = (genome.get("mood") or "").lower()
                if any(t in _gmood for t in ("sad", "dark", "melanchol", "low", "tense", "moody")):
                    _mood_def = _mood_opts[0]
                elif any(t in _gmood for t in ("happy", "bright", "uplift", "joy", "warm", "energ")):
                    _mood_def = _mood_opts[2]
                else:
                    _mood_def = _mood_opts[1]
                _mood = st.select_slider("Mood direction", options=_mood_opts, value=_mood_def, key="reph_mood")
                _rhyme = st.select_slider(
                    "Rhyme structure",
                    options=["tight couplets (AABB)", "alternating (ABAB)",
                             "enclosed / looser (ABBA)", "loose / slant rhyme"],
                    value="alternating (ABAB)", key="reph_rhyme")
                _ref_artists = list((rp or {}).get("artists", []) or [])
                _active_artist = st.selectbox("Reference direction",
                                              ["No specific artist"] + _ref_artists, key="reph_artist")

                _rb1, _rb2 = st.columns(2)
                if _rb1.button("✨ Rephrase", type="primary", key="do_rephrase", use_container_width=True):
                    with st.spinner("Rephrasing on the melody..."):
                        st.session_state.rephrase_candidate = rephrase_selection(
                            st.session_state.selected_text, _audit, _ctx,
                            mood_target=_mood, rhyme_structure=_rhyme,
                            active_reference_artist=(None if _active_artist == "No specific artist"
                                                     else _active_artist),
                            provider=get_llm_provider(),
                        )

                _cand = st.session_state.rephrase_candidate
                _apply_clicked = _rb2.button("⬇ Apply", key="do_apply", use_container_width=True,
                                             disabled=not (_cand and _cand.get("candidate")))

                if _cand and _cand.get("candidate"):
                    _csrc = _cand.get("source")
                    if _csrc == "openai":
                        st.success("Suggested rewrite (OpenAI):")
                    elif _csrc == "openai_fallback_heuristic":
                        st.warning("Live LLM unavailable — heuristic rewrite:")
                    else:
                        st.warning("Heuristic rewrite (no live LLM configured):")
                    for _cl in _cand["candidate"].splitlines():
                        st.text(_cl)
                    _exp = _cand.get("explanation", {})
                    with st.expander("Why this rewrite"):
                        for _ek in ("metric", "mood", "rhyme", "reference", "safety"):
                            if _exp.get(_ek):
                                st.caption(f"**{_ek.title()}:** {_exp[_ek]}")
                    _mrep = _cand.get("metric_report", {})
                    if _mrep.get("target_syllable_range"):
                        _ok = _mrep.get("all_in_range")
                        (st.success if _ok else st.warning)(
                            f"Metric target {_mrep['target_syllable_range'][0]}–{_mrep['target_syllable_range'][1]} syl/line"
                            + (" · all lines fit" if _ok else " · some lines off — try Rephrase again"))
                    st.caption(":green[Original text only — no copyrighted lyrics or imitation.]")

                if _apply_clicked and _cand and _cand.get("candidate"):
                    _rng = st.session_state.selection_line_range
                    _newsel = _cand["candidate"]
                    _raw = st.session_state.lyrics_saved.splitlines()
                    _done = False
                    if _rng and 0 <= _rng[0] <= _rng[1] < len(_raw):
                        _raw[_rng[0]:_rng[1] + 1] = (_newsel.splitlines() or [_newsel])
                        st.session_state.lyrics_saved = "\n".join(_raw)
                        _done = True
                    elif st.session_state.lyrics_saved.count(st.session_state.selected_text) == 1:
                        st.session_state.lyrics_saved = st.session_state.lyrics_saved.replace(
                            st.session_state.selected_text, _newsel, 1)
                        _done = True
                    if _done:
                        st.session_state.pop("studio_lyrics", None)
                        st.session_state.rephrase_candidate = None
                        st.session_state.selected_text = ""
                        st.session_state.selection_audit = None
                        st.session_state.selection_line_range = None
                        _nt = st.session_state.lyrics_saved
                        if st.session_state.prosody_result is not None:
                            st.session_state.prosody_result = analyze_lines_prosody(
                                _nt, st.session_state.project_meta.get("language", "auto"))
                            st.session_state.lyrics_result = analyze_lyrics(_nt)
                        if st.session_state.mining_result is not None:
                            st.session_state.mining_result = mine_text(_nt)
                        st.session_state.apply_confirm = "Applied to lyrics editor."
                        st.rerun()
                    else:
                        st.warning("Couldn't locate the exact selection (it may appear multiple times). "
                                   "Click the specific line/block again, then Apply.")

    # ── Metric Draft Scaffold (AI, melody-aware, copyright-safe) ──
    # Secondary tool: draft/rewrite a whole section ON the melody. The primary
    # interaction above is Select → Audit → Rephrase → Apply.
    st.markdown("---")
    _llm = llm_status()
    with st.container(border=True):
        st.markdown("#### 🎼 Metric Draft Scaffold — draft lyrics on the melody (copyright-safe)")
        st.caption("Not a song generator: this scaffolds a draft that respects your melody metric. "
                   "Refine it line-by-line with the audit above.")
        if _llm["status"] == "live":
            st.caption(f":green[LLM live — {_llm['provider']} · {_llm['model']}]")
        else:
            st.caption(f":orange[LLM mock ({_llm.get('reason') or 'not configured'}) — "
                       "a heuristic placeholder draft will be produced. "
                       "Add OPENAI_API_KEY to .env for real generation.]")

        _has_lyrics = bool((st.session_state.lyrics_saved or "").strip())
        _vm = st.session_state.vocal_midi
        _targets = line_syllable_targets(_vm)
        _wb = st.session_state.writing_brief
        if _targets:
            st.caption(f":green[Melody metric active: {len(_targets)} phrases → syllable targets {_targets}]")
            _vph = (_vm or {}).get("phrase_estimates") or []
            if _vph:
                with st.expander("How the melody maps to line targets (note → slot)"):
                    for p in _vph:
                        st.text(
                            f"  Line {p.get('index', 0) + 1}: {p.get('n_notes', 0)} notes "
                            f"→ target {p.get('syllable_slots', 0)} syllables"
                        )
                    st.caption("These targets are sent to OpenAI; generated lines are re-checked against them.")
        else:
            st.caption(":orange[No vocal MIDI — generation uses even, singable lines (heuristic metric).]")
        if _has_lyrics:
            st.caption("Existing lyrics detected → mode: **rewrite/continue on the melody**.")
        elif _wb and _wb.get("core_theme"):
            st.caption(f"Using Writing Brief (Mode B) → theme: **{_wb['core_theme']}**.")
        else:
            st.caption("Tip: create a Writing Brief in **Lyrics Prompter → Mode B**, or paste lyrics in Mode A.")

        cg1, cg2 = st.columns([2, 1])
        _gen_mode = "rewrite" if _has_lyrics else "generate"
        _gen_label = "Rewrite draft on melody" if _has_lyrics else "Draft on melody"
        _do_gen = cg1.button(f"🎼 {_gen_label}", key="btn_compose")
        _temp = cg2.slider("Creativity", 0.2, 1.2, 0.85, 0.05, key="compose_temp")

        if _do_gen:
            if not _has_lyrics and not (_wb and _wb.get("core_theme")):
                st.warning("Nothing to compose from yet. Add lyrics (Mode A) or a Writing Brief (Mode B) first.")
            else:
                _g = build_song_genome_summary(
                    st.session_state.mgx_output, st.session_state.cyanite_result,
                    st.session_state.vocal_midi, st.session_state.cyanite_source,
                ) if st.session_state.mgx_output else {}
                brief = build_composition_brief(
                    genome=_g, vocal_midi=_vm, writing_brief=_wb,
                    reference_profile=st.session_state.reference_profile,
                    existing_lyrics=st.session_state.lyrics_saved or "",
                    language=st.session_state.project_meta.get("language", "auto"),
                    mining=st.session_state.mining_result,
                )
                provider = get_llm_provider()
                with st.spinner("Composing a melody-aware draft..."):
                    try:
                        draft = compose_draft(
                            provider, brief,
                            existing_lyrics=st.session_state.lyrics_saved or "",
                            mode=_gen_mode, temperature=_temp,
                        )
                    except Exception as exc:  # noqa: BLE001
                        draft = None
                        st.error(f"Draft generation failed: {exc}")
                if draft:
                    st.session_state.generated_draft = draft
                    st.session_state.composition_brief = brief

        draft = st.session_state.generated_draft
        if draft:
            src = draft.get("source")
            if src == "mock_heuristic":
                st.warning("Heuristic placeholder draft (no live LLM). Configure OPENAI_API_KEY for real lyrics.")
            else:
                st.success(f"Draft generated via {src}" + (f" · {draft.get('model')}" if draft.get("model") else "")
                           + (" · tightened to metric" if draft.get("tightened") else ""))
            if draft.get("title"):
                st.markdown(f"**{draft['title']}**")
            for sec in draft.get("sections", []):
                st.markdown(f"*[{(sec.get('type') or 'section').title()}]*")
                for ln in sec.get("lines", []):
                    st.text(ln)
            mr = draft.get("metric_report") or {}
            if mr.get("melody_aligned"):
                fr = mr.get("fit_ratio")
                badge = st.success if (fr or 0) >= 0.8 else st.warning
                badge(f"Metric fit (verse vs melody): {int((fr or 0)*100)}% of lines within ±1 syllable "
                      f"({mr.get('mismatches')} off).")
                with st.expander("Per-line metric check"):
                    for r in mr.get("rows", []):
                        tgt = r.get("target_syllables")
                        mark = "✅" if r.get("fit") else ("⚠️" if tgt is not None else "·")
                        st.text(f'{mark} got {r["actual_syllables"]:>2}'
                                + (f" / need {tgt:>2}" if tgt is not None else "")
                                + '  | ' + str(r["line"]))
            if draft.get("notes"):
                st.caption(draft["notes"])
            st.caption(":green[Original draft — you remain the author. No copyrighted text reproduced.]")

            uc1, uc2 = st.columns(2)
            if uc1.button("⬇ Use this draft in the editor", key="use_draft"):
                st.session_state.lyrics_saved = draft_to_text(draft)
                st.session_state.pop("studio_lyrics", None)
                st.session_state.selected_text = ""
                st.session_state.selection_audit = None
                st.session_state.selection_line_range = None
                st.session_state.rephrase_candidate = None
                st.rerun()
            if uc2.button("🔄 Regenerate all", key="regen_draft"):
                st.session_state.generated_draft = None
                st.rerun()

            _sec_types = [s.get("type") for s in draft.get("sections", []) if s.get("type")]
            if _sec_types:
                rc1, rc2 = st.columns([2, 1])
                _sec_pick = rc1.selectbox("Regenerate a single section", _sec_types, key="regen_sec_pick")
                if rc2.button("↻ Regenerate section", key="regen_sec_btn"):
                    brief = st.session_state.composition_brief or build_composition_brief(
                        genome=(build_song_genome_summary(
                            st.session_state.mgx_output, st.session_state.cyanite_result,
                            st.session_state.vocal_midi, st.session_state.cyanite_source) if st.session_state.mgx_output else {}),
                        vocal_midi=_vm, writing_brief=_wb,
                        reference_profile=st.session_state.reference_profile,
                        existing_lyrics=st.session_state.lyrics_saved or "",
                        language=st.session_state.project_meta.get("language", "auto"),
                        mining=st.session_state.mining_result,
                    )
                    with st.spinner(f"Regenerating {_sec_pick}..."):
                        new_sec = regenerate_section(get_llm_provider(), brief, _sec_pick, temperature=_temp)
                    for i, s in enumerate(draft["sections"]):
                        if s.get("type") == _sec_pick:
                            draft["sections"][i] = new_sec
                            break
                    from src.draft_composer import validate_metric
                    draft["metric_report"] = validate_metric(draft, brief)
                    st.session_state.generated_draft = draft
                    st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# TAB 5 — EXPORT
# ═════════════════════════════════════════════════════════════════════════════
with tab_export:
    st.header("Export")
    ensure_dir(OUTPUTS_DIR)

    has_mgx = st.session_state.mgx_output is not None
    has_mining = st.session_state.mining_result is not None
    has_audit = bool(st.session_state.selection_audit) or bool(st.session_state.generated_draft)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("MGX", "ready" if has_mgx else "—")
    c2.metric("Text Mining", "ready" if has_mining else "—")
    c3.metric("Reference", "ready" if st.session_state.reference_profile else "—")
    c4.metric("Writing Studio", "ready" if has_audit else "—")

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
