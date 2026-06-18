"""Song Genome Summary + readable Librettist markdown report."""
from __future__ import annotations

from typing import Any


def _pretty_cyanite_key(value: Any) -> Any:
    """Turn a Cyanite MusicalKey enum (e.g. 'cSharpMinor') into 'C# minor'."""
    if not value or not isinstance(value, str):
        return value
    s = value.replace("Sharp", "#").replace("Flat", "b")
    for mode in ("Major", "Minor"):
        if s.endswith(mode):
            root = s[: -len(mode)]
            if root:
                root = root[0].upper() + root[1:]
            return f"{root} {mode.lower()}"
    return s


def _cyanite_view(cyanite: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize either the live-Cyanite descriptor shape or the mock shape."""
    c = cyanite or {}
    is_real = (
        any(k in c for k in ("genre_tags", "mood_tags", "energy_level", "caption", "instrument_tags"))
        or isinstance(c.get("key"), dict) or isinstance(c.get("bpm"), dict)
    )
    if is_real:
        key = c.get("key") or {}
        bpm = c.get("bpm") or {}
        moods = c.get("mood_tags") or c.get("mood_advanced_tags") or []
        genres = c.get("genre_tags") or []
        return {
            "mood": moods[0] if moods else None,
            "moods": moods,
            "energy": c.get("energy_level"),
            "valence": c.get("valence"),
            "arousal": c.get("arousal"),
            "genre": genres[0] if genres else None,
            "genres": genres,
            "subgenres": c.get("subgenre_tags") or [],
            "instrumentation": c.get("instrument_tags") or [],
            "bpm": bpm.get("value"),
            "bpm_confidence": bpm.get("confidence"),
            "key": _pretty_cyanite_key(key.get("value")),
            "key_confidence": key.get("confidence"),
            "time_signature": c.get("time_signature"),
            "caption": c.get("caption"),
        }
    # mock shape
    return {
        "mood": c.get("mood_primary"),
        "moods": [m for m in [c.get("mood_primary"), c.get("mood_secondary")] if m],
        "energy": c.get("energy"),
        "valence": c.get("valence"),
        "arousal": c.get("arousal"),
        "genre": c.get("genre_primary"),
        "genres": [g for g in [c.get("genre_primary"), c.get("genre_secondary")] if g],
        "subgenres": [],
        "instrumentation": c.get("instrumentation") or c.get("tags") or [],
        "bpm": None, "bpm_confidence": None,
        "key": None, "key_confidence": None,
        "time_signature": None, "caption": None,
    }


def build_song_genome_summary(
    mgx: dict[str, Any] | None,
    cyanite: dict[str, Any] | None = None,
    vocal_midi: dict[str, Any] | None = None,
    cyanite_source: str | None = None,
) -> dict[str, Any]:
    """Compact, human-facing summary merging MGX (local) + Cyanite descriptors."""
    mgx = mgx or {}
    R = mgx.get("R", {})
    M = mgx.get("M", {})
    H = mgx.get("H", {})
    F = mgx.get("F", {})
    C = mgx.get("C", {})
    cv = _cyanite_view(cyanite)

    warnings: list[str] = []
    if isinstance(mgx.get("meta"), dict):
        warnings.extend(mgx["meta"].get("notes", []) or [])

    mgx_bpm = R.get("bpm")
    mgx_key = H.get("key_center", H.get("key"))
    mgx_mode = H.get("key_mode", H.get("mode"))
    mgx_key_conf = H.get("key_confidence", H.get("mode_confidence"))
    mgx_key_str = (f"{mgx_key} {mgx_mode}".strip() if mgx_key else None)

    # "chosen" prefers MGX (local structural analysis), falls back to Cyanite.
    chosen_bpm = mgx_bpm if isinstance(mgx_bpm, (int, float)) else cv["bpm"]
    chosen_key = mgx_key_str or cv["key"]

    # Flag BPM divergence (ignoring half/double-time ambiguity).
    if isinstance(mgx_bpm, (int, float)) and isinstance(cv["bpm"], (int, float)) and cv["bpm"]:
        ratio = mgx_bpm / cv["bpm"]
        if not (0.95 <= ratio <= 1.05 or 0.47 <= ratio <= 0.53 or 1.9 <= ratio <= 2.1):
            warnings.append(f"BPM mismatch: MGX {round(mgx_bpm)} vs Cyanite {round(cv['bpm'])}.")

    contour = M.get("contour_direction") or M.get("contour_summary") or "n/a"
    summary = {
        # chosen / backward-compatible top-level fields
        "bpm": chosen_bpm,
        "time_signature": R.get("time_signature") or cv["time_signature"],
        "key": mgx_key,
        "mode": mgx_mode,
        "key_confidence": mgx_key_conf,
        # source comparison
        "bpm_sources": {"mgx": mgx_bpm, "cyanite": cv["bpm"], "chosen": chosen_bpm},
        "key_sources": {"mgx": mgx_key_str, "cyanite": cv["key"], "chosen": chosen_key},
        # Cyanite descriptors
        "mood": cv["mood"],
        "moods": cv["moods"],
        "energy": cv["energy"],
        "valence": cv["valence"],
        "arousal": cv["arousal"],
        "genre": cv["genre"],
        "genres": cv["genres"],
        "subgenres": cv["subgenres"],
        "instrumentation": cv["instrumentation"],
        "cyanite_caption": cv["caption"],
        "cyanite_source": cyanite_source,
        # MGX structural
        "form_sections": F.get("section_sequence", F.get("sections")),
        "melodic_contour": contour,
        "harmonic_summary": {
            "harmonic_change_rate": H.get("harmonic_change_rate"),
            "relative_chord_functions": H.get("relative_chord_functions"),
        },
        "overall_confidence": C.get("overall_confidence"),
        "warnings": warnings,
    }
    if vocal_midi and vocal_midi.get("n_notes"):
        summary["vocal_midi"] = {
            "n_notes": vocal_midi.get("n_notes"),
            "suggested_syllable_slots": vocal_midi.get("suggested_syllable_slots"),
            "cadence_profile": vocal_midi.get("cadence_profile"),
            "melodic_range": vocal_midi.get("melodic_range"),
        }
    return summary


def _section(title: str) -> str:
    return f"\n## {title}\n\n"


def generate_librettist_report(project: dict[str, Any]) -> str:
    """Render the unified project state as a readable markdown report."""
    meta = project.get("project_meta", {})
    analysis = project.get("analysis", {})
    inputs = project.get("inputs", {})
    studio = project.get("writing_studio", {})

    mgx = analysis.get("mgx", {})
    cyanite = analysis.get("cyanite", {})
    genome = build_song_genome_summary(mgx, cyanite, analysis.get("vocal_midi"),
                                       analysis.get("cyanite_source"))

    lines: list[str] = []
    lines.append("# MGX Librettist — Project Report\n")
    lines.append(f"**Title:** {meta.get('title') or 'Untitled'}  ")
    lines.append(f"**Language:** {meta.get('language') or 'auto'}  ")
    lines.append(f"**Created:** {meta.get('created_at') or '-'}  ")
    lines.append(f"**Provider mode:** {meta.get('provider_mode', 'mock')}\n")

    # Song Genome Summary
    lines.append(_section("Song Genome Summary"))
    bs = genome.get("bpm_sources", {}); ks = genome.get("key_sources", {})
    lines.append(f"- BPM (chosen): {genome.get('bpm')} — MGX: {bs.get('mgx')} · Cyanite: {bs.get('cyanite')}")
    lines.append(f"- Time signature: {genome.get('time_signature')}")
    lines.append(f"- Key (chosen): {ks.get('chosen')} — MGX: {ks.get('mgx')} · Cyanite: {ks.get('cyanite')}")
    lines.append(f"- Mood / energy / valence / arousal: {genome.get('mood')} / {genome.get('energy')} / {genome.get('valence')} / {genome.get('arousal')}")
    _genres = genome.get("genres") or ([genome.get("genre")] if genome.get("genre") else [])
    if _genres:
        lines.append(f"- Genre: {', '.join(g for g in _genres if g)}"
                     + (f" · subgenre: {', '.join(genome.get('subgenres'))}" if genome.get("subgenres") else ""))
    if genome.get("instrumentation"):
        lines.append(f"- Instrumentation: {', '.join(genome.get('instrumentation'))}")
    lines.append(f"- Melodic contour: {genome.get('melodic_contour')}")
    lines.append(f"- Form: {genome.get('form_sections')}")
    if genome.get("cyanite_source"):
        lines.append(f"- Cyanite source: {genome.get('cyanite_source')}")
    if genome.get("vocal_midi"):
        vm = genome["vocal_midi"]
        lines.append(f"- Vocal MIDI: {vm.get('n_notes')} notes, ~{vm.get('suggested_syllable_slots')} syllable slots, cadence: {vm.get('cadence_profile')}")

    # Lyrics Summary
    lyrics_struct = analysis.get("lyrics_structure", {})
    prosody = analysis.get("lyrics_prosody", {})
    if lyrics_struct or prosody:
        lines.append(_section("Lyrics Summary"))
        if lyrics_struct:
            lines.append(f"- Lines: {lyrics_struct.get('n_lines')}, Stanzas: {lyrics_struct.get('n_stanzas')}, Words: {lyrics_struct.get('n_words')}")
        if prosody:
            lines.append(f"- Avg syllables/line: {prosody.get('average_syllables_per_line')} (variance {prosody.get('syllable_variance')})")
            rc = prosody.get("rhyme_candidates", [])
            if rc:
                lines.append(f"- Rhyme groups detected: {len(rc)}")

    # Writing Brief
    brief = analysis.get("writing_brief", {})
    if brief and brief.get("core_theme"):
        lines.append(_section("Writing Brief"))
        lines.append(f"- Core theme: {brief.get('core_theme')}")
        lines.append(f"- Emotional temperature: {brief.get('emotional_temperature')}")
        if brief.get("possible_titles"):
            lines.append(f"- Title seeds: {', '.join(brief['possible_titles'])}")
        if brief.get("promising_images"):
            lines.append(f"- Promising images: {'; '.join(brief['promising_images'])}")
        if brief.get("images_to_avoid"):
            lines.append(f"- Images to avoid: {'; '.join(brief['images_to_avoid'])}")

    # Reference Profile
    ref = analysis.get("reference_profile", {})
    if ref and ref.get("artists"):
        lines.append(_section("Reference Profile — copyright-safe abstraction"))
        lines.append(f"- Artists referenced: {', '.join(ref.get('artists', []))}")
        ap = ref.get("abstract_patterns", {})
        lines.append(f"- Narrative stance: {ap.get('narrative_stance')}")
        lines.append(f"- Imagery density: {ap.get('imagery_density')}")
        lines.append(f"- Verse style: {ap.get('verse_style')}")
        lines.append(f"- Chorus style: {ap.get('chorus_style')}")
        for rule in ref.get("safe_inspiration_rules", []):
            lines.append(f"  - {rule}")

    # Line / Block Audit (Writing Studio)
    audit = studio.get("selection_audit", {})
    if audit and audit.get("scores"):
        lines.append(_section("Line / Block Audit"))
        lines.append(f"- Selection: \"{studio.get('selected_text', '')[:80]}\" ({audit.get('selection_type', '')})")
        if audit.get("summary_blurb"):
            lines.append(f"- Summary: {audit['summary_blurb']}")
        sc = audit.get("scores", {})
        _order = ["metric_fit", "stress_alignment", "singability", "mood_alignment",
                  "rhyme_structure", "imagery_strength", "reference_alignment", "cliche_risk"]
        scored = "; ".join(f"{k.replace('_', ' ')}: {sc[k]}/100" for k in _order if k in sc)
        if scored:
            lines.append(f"- Scores: {scored}")

    # Warnings
    if genome.get("warnings"):
        lines.append(_section("Warnings"))
        for w in genome["warnings"]:
            lines.append(f"- {w}")

    # Copyright safety
    lines.append(_section("Copyright Safety"))
    lines.append(
        "This report uses references only as abstract, copyright-safe patterns. "
        "It does not reproduce copyrighted lyrics or imitate specific artists. "
        "The songwriter remains the sole author of the work."
    )

    return "\n".join(lines) + "\n"
