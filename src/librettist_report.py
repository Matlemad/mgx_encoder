"""Song Genome Summary + readable Librettist markdown report."""
from __future__ import annotations

from typing import Any


def build_song_genome_summary(
    mgx: dict[str, Any] | None,
    cyanite: dict[str, Any] | None = None,
    vocal_midi: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compact, human-facing summary of the song's musical genome."""
    mgx = mgx or {}
    cyanite = cyanite or {}
    R = mgx.get("R", {})
    M = mgx.get("M", {})
    H = mgx.get("H", {})
    F = mgx.get("F", {})
    C = mgx.get("C", {})

    warnings: list[str] = []
    if isinstance(mgx.get("meta"), dict):
        warnings.extend(mgx["meta"].get("notes", []) or [])

    contour = M.get("contour_direction") or M.get("contour_summary") or "n/a"
    summary = {
        "bpm": R.get("bpm"),
        "time_signature": R.get("time_signature"),
        "key": H.get("key_center", H.get("key")),
        "mode": H.get("key_mode", H.get("mode")),
        "key_confidence": H.get("key_confidence", H.get("mode_confidence")),
        "mood": cyanite.get("mood_primary"),
        "energy": cyanite.get("energy"),
        "valence": cyanite.get("valence"),
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
    genome = build_song_genome_summary(mgx, cyanite, analysis.get("vocal_midi"))

    lines: list[str] = []
    lines.append("# MGX Librettist — Project Report\n")
    lines.append(f"**Title:** {meta.get('title') or 'Untitled'}  ")
    lines.append(f"**Language:** {meta.get('language') or 'auto'}  ")
    lines.append(f"**Created:** {meta.get('created_at') or '-'}  ")
    lines.append(f"**Provider mode:** {meta.get('provider_mode', 'mock')}\n")

    # Song Genome Summary
    lines.append(_section("Song Genome Summary"))
    lines.append(f"- BPM: {genome.get('bpm')}")
    lines.append(f"- Time signature: {genome.get('time_signature')}")
    lines.append(f"- Key / mode: {genome.get('key')} {genome.get('mode')} (confidence: {genome.get('key_confidence')})")
    lines.append(f"- Mood / energy / valence: {genome.get('mood')} / {genome.get('energy')} / {genome.get('valence')}")
    lines.append(f"- Melodic contour: {genome.get('melodic_contour')}")
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

    # Palette Results
    palette = studio.get("palette_outputs", {})
    if palette:
        lines.append(_section("Palette Results"))
        lines.append(f"- Selection: \"{studio.get('selected_text', '')[:80]}\" ({studio.get('selection_type', '')})")
        for key, val in palette.items():
            if key.startswith("_") or not isinstance(val, dict):
                continue
            title = val.get("module", key)
            lines.append(f"- **{title}**")

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
