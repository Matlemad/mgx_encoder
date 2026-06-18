"""Draft Composer — melody-aware, copyright-safe AI lyric generation.

Combines everything the app already knows about a song:
- musical genome (MGX + Cyanite): bpm, key, mode, mood, energy, genre
- vocal MIDI metric: per-phrase syllable slots, strong positions, cadence
- creative intent: a Mode B writing brief OR existing Mode A lyrics
- abstract reference profile (Musixmatch) — inspiration only, never copied

It produces an ORIGINAL structured draft that tries to sit on the melody's
metric. Real generation uses an LLM provider; when none is configured it falls
back to a transparent heuristic so the flow still works offline.

Copyright safety: the system prompt forbids reproducing any existing lyrics,
and reference material is passed only as abstract descriptors.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .lyrics_editor import detect_language, estimate_syllables

_SYSTEM_PROMPT = (
    "You are a professional songwriting collaborator. You write ORIGINAL lyrics.\n"
    "Hard rules:\n"
    "1. Never reproduce, quote, or closely paraphrase any existing copyrighted song. "
    "Reference artists are provided ONLY as abstract stylistic direction, never to imitate specific lines.\n"
    "2. The songwriter remains the sole author; you produce a draft they will edit.\n"
    "3. Respect the requested syllable counts per line as closely as possible so the "
    "words fit the existing melody.\n"
    "4. Honour the requested language.\n"
    "5. Output STRICT JSON only, no commentary, matching the requested schema."
)


# ──────────────────────────────────────────────────────────────────────────────
# Metric targets from the vocal MIDI (or sensible defaults)
# ──────────────────────────────────────────────────────────────────────────────
def line_syllable_targets(vocal_midi: dict[str, Any] | None) -> list[int]:
    """Ordered per-line syllable targets derived from MIDI phrases."""
    if not vocal_midi:
        return []
    phrases = vocal_midi.get("phrase_estimates") or []
    targets = [int(p.get("syllable_slots", 0)) for p in phrases if p.get("syllable_slots")]
    # Keep targets in a singable range to avoid degenerate 1-syllable phrases.
    return [max(2, min(16, t)) for t in targets]


def _count_line_syllables(line: str, language: str) -> int:
    words = re.findall(r"[a-zA-Zàèéìòùáéíóúüñ']+", line)
    return sum(estimate_syllables(w, language) for w in words)


# ──────────────────────────────────────────────────────────────────────────────
# Composition brief (the structured context handed to the LLM)
# ──────────────────────────────────────────────────────────────────────────────
def _mining_signals(mining: dict[str, Any] | None) -> dict[str, Any]:
    """Extract the abstract text-mining signals worth feeding to the LLM."""
    if not mining:
        return {}
    wf = mining.get("word_frequencies") or {}
    bg = mining.get("bigrams") or {}
    co = mining.get("cooccurrences") or {}
    return {
        "top_words": list(wf.keys())[:12],
        "top_bigrams": list(bg.keys())[:8],
        "top_cooccurrences": list(co.keys())[:6],
        "n_tokens": mining.get("n_filtered_tokens"),
    }


def build_composition_brief(
    genome: dict[str, Any] | None = None,
    vocal_midi: dict[str, Any] | None = None,
    writing_brief: dict[str, Any] | None = None,
    reference_profile: dict[str, Any] | None = None,
    existing_lyrics: str = "",
    language: str = "auto",
    mining: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble a compact, copyright-safe brief for generation."""
    genome = genome or {}
    writing_brief = writing_brief or {}
    ref = reference_profile or {}
    ref_patterns = ref.get("abstract_patterns", {}) if isinstance(ref, dict) else {}

    if language == "auto":
        seed = existing_lyrics or writing_brief.get("core_theme", "") or " ".join(
            writing_brief.get("lexical_fields", []) or []
        )
        language = detect_language(seed) if seed else "en"

    targets = line_syllable_targets(vocal_midi)

    return {
        "language": language,
        "music": {
            "bpm": genome.get("bpm"),
            "time_signature": genome.get("time_signature"),
            "key": genome.get("key"),
            "mode": genome.get("mode"),
            "mood": genome.get("mood"),
            "moods": genome.get("moods") or [],
            "energy": genome.get("energy"),
            "valence": genome.get("valence"),
            "arousal": genome.get("arousal"),
            "genres": genome.get("genres") or [],
            "subgenres": genome.get("subgenres") or [],
            "instrumentation": genome.get("instrumentation") or [],
            "form_sections": genome.get("form_sections"),
        },
        "metric": {
            "line_syllable_targets": targets,
            "n_lines": len(targets),
            "cadence": (vocal_midi or {}).get("cadence_profile"),
            "melodic_range_semitones": ((vocal_midi or {}).get("melodic_range") or {}).get("range_semitones"),
            "has_vocal_midi": bool(targets),
        },
        "intent": {
            "core_theme": writing_brief.get("core_theme"),
            "emotional_temperature": writing_brief.get("emotional_temperature"),
            "point_of_view_options": writing_brief.get("point_of_view_options", []),
            "possible_scenes": writing_brief.get("possible_scenes", []),
            "lexical_fields": writing_brief.get("lexical_fields", []),
            "images_to_avoid": writing_brief.get("images_to_avoid", []),
            "promising_images": writing_brief.get("promising_images", []),
            "possible_titles": writing_brief.get("possible_titles", []),
            "chorus_concepts": writing_brief.get("chorus_concepts", []),
        },
        "reference_abstract": {
            "common_themes": ref_patterns.get("common_themes", []),
            "dominant_moods": ref_patterns.get("dominant_moods", []),
            "narrative_stance": ref_patterns.get("narrative_stance"),
            "imagery_density": ref_patterns.get("imagery_density"),
            "source": ref.get("source"),
        },
        "lyric_signals": _mining_signals(mining),
        "existing_lyrics_present": bool(existing_lyrics.strip()),
    }


# ──────────────────────────────────────────────────────────────────────────────
# Prompt construction
# ──────────────────────────────────────────────────────────────────────────────
def _user_prompt(brief: dict[str, Any], existing_lyrics: str, mode: str) -> str:
    music = brief["music"]
    metric = brief["metric"]
    intent = brief["intent"]
    ref = brief["reference_abstract"]
    lang = brief["language"]

    lines: list[str] = []
    lines.append(f"Write original song lyrics in language: {lang}.")
    lines.append("")
    lines.append("MUSICAL CONTEXT (align tone to it, contrast deliberately if you do):")
    _ts = f", time signature: {music.get('time_signature')}" if music.get("time_signature") else ""
    lines.append(f"- tempo: {music.get('bpm')} BPM, key: {music.get('key')} {music.get('mode') or ''}{_ts}".rstrip())
    lines.append(f"- mood: {music.get('mood')}"
                 + (f" ({', '.join(music.get('moods')[:4])})" if music.get("moods") else "")
                 + f", energy: {music.get('energy')}")
    _va = []
    if music.get("valence") is not None:
        _va.append(f"valence: {music['valence']}")
    if music.get("arousal") is not None:
        _va.append(f"arousal: {music['arousal']}")
    if _va:
        lines.append("- " + ", ".join(_va) + " (emotional positivity / intensity)")
    _gen = ", ".join((music.get("genres") or []) + (music.get("subgenres") or [])) or "n/a"
    lines.append(f"- genres: {_gen}")
    if music.get("instrumentation"):
        lines.append(f"- instrumentation: {', '.join(music['instrumentation'][:6])} — let the imagery suit this palette")
    if music.get("form_sections"):
        _fs = music["form_sections"]
        _fs = " ".join(map(str, _fs)) if isinstance(_fs, list) else str(_fs)
        lines.append(f"- song form (from audio): {_fs}")
    lines.append("")

    if metric.get("has_vocal_midi"):
        targets = metric["line_syllable_targets"]
        lines.append("MELODY METRIC (critical — match syllables per line, in order):")
        lines.append(f"- the melody has {len(targets)} sung phrases.")
        lines.append(f"- syllable target per line, in order: {targets}")
        lines.append(f"- the FIRST section ('verse') MUST have exactly {len(targets)} lines, "
                     "each with a syllable count within ±1 of the corresponding target.")
        if metric.get("cadence"):
            lines.append(f"- melodic cadence: {metric['cadence']} — shape the final line's resolution accordingly.")
    else:
        lines.append("MELODY METRIC: no vocal MIDI provided. Keep lines singable and even "
                     "(roughly 6–9 syllables), 4 lines per section.")
    lines.append("")

    lines.append("CREATIVE INTENT:")
    if intent.get("core_theme"):
        lines.append(f"- core theme: {intent['core_theme']}")
    if intent.get("emotional_temperature"):
        lines.append(f"- emotional temperature: {intent['emotional_temperature']}")
    if intent.get("point_of_view_options"):
        lines.append(f"- point of view (pick one): {', '.join(intent['point_of_view_options'][:3])}")
    if intent.get("possible_scenes"):
        lines.append(f"- candidate scenes: {'; '.join(intent['possible_scenes'][:3])}")
    if intent.get("lexical_fields"):
        lines.append(f"- lexical fields to draw on: {', '.join(intent['lexical_fields'][:8])}")
    if intent.get("promising_images"):
        lines.append(f"- promising original images: {'; '.join(intent['promising_images'][:3])}")
    if intent.get("images_to_avoid"):
        lines.append(f"- clichés to AVOID: {', '.join(intent['images_to_avoid'][:5])}")
    if intent.get("chorus_concepts"):
        lines.append(f"- chorus concept ideas: {'; '.join(intent['chorus_concepts'][:2])}")
    lines.append("")

    if any(ref.get(k) for k in ("common_themes", "dominant_moods", "narrative_stance")):
        lines.append("REFERENCE DIRECTION (abstract inspiration only — DO NOT imitate specific lines):")
        if ref.get("narrative_stance"):
            lines.append(f"- narrative stance to try: {ref['narrative_stance']}")
        if ref.get("common_themes"):
            lines.append(f"- recurring abstract themes: {', '.join(ref['common_themes'][:5])}")
        if ref.get("dominant_moods"):
            lines.append(f"- dominant moods: {', '.join(ref['dominant_moods'][:4])}")
        lines.append("")

    signals = brief.get("lyric_signals") or {}
    if signals.get("top_words"):
        lines.append("LYRIC VOCABULARY (from the author's own text mining — stay in this register, vary clichés):")
        lines.append(f"- frequent words: {', '.join(signals['top_words'])}")
        if signals.get("top_bigrams"):
            lines.append(f"- frequent word pairs: {', '.join(signals['top_bigrams'])}")
        if signals.get("top_cooccurrences"):
            lines.append(f"- co-occurring pairs: {', '.join(signals['top_cooccurrences'])}")
        lines.append("")

    if mode == "rewrite" and existing_lyrics.strip():
        lines.append("EXISTING DRAFT (the author's own words — rewrite/continue them to fit the "
                     "melody metric and tone; keep their meaning and authorship, improve singability):")
        lines.append(existing_lyrics.strip()[:2000])
        lines.append("")

    lines.append("OUTPUT JSON SCHEMA (strict):")
    lines.append(
        '{"title": str, "language": str, "sections": '
        '[{"type": "verse"|"pre-chorus"|"chorus"|"bridge", "lines": [str, ...]}], '
        '"notes": str}'
    )
    lines.append("Include at least a verse and a chorus. Return ONLY the JSON object.")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# JSON parsing helpers
# ──────────────────────────────────────────────────────────────────────────────
def _parse_json_draft(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None
    text = raw.strip()
    # strip ```json ... ``` fences if present
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:  # noqa: BLE001
                return None
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Heuristic fallback composer (offline / no LLM)
# ──────────────────────────────────────────────────────────────────────────────
def _heuristic_draft(brief: dict[str, Any]) -> dict[str, Any]:
    intent = brief["intent"]
    metric = brief["metric"]
    images = (intent.get("promising_images") or []) + (intent.get("possible_scenes") or [])
    fields = intent.get("lexical_fields") or ["light", "distance", "time"]
    title = (intent.get("possible_titles") or ["Untitled Draft"])[0]
    targets = metric.get("line_syllable_targets") or [8, 8, 8, 8]

    def _filler(i: int) -> str:
        img = images[i % len(images)] if images else fields[i % len(fields)]
        return f"[draft] {img}"

    verse_lines = [_filler(i) for i in range(len(targets) or 4)]
    chorus_seed = (intent.get("chorus_concepts") or ["a repeated image"])[0]
    chorus_lines = [f"[draft chorus] {chorus_seed}"] * 2 + [f"[draft] {fields[0]}"]

    return {
        "title": title,
        "language": brief["language"],
        "sections": [
            {"type": "verse", "lines": verse_lines},
            {"type": "chorus", "lines": chorus_lines},
        ],
        "notes": "Heuristic placeholder draft (no live LLM). Configure OPENAI_API_KEY for real generation.",
        "source": "mock_heuristic",
        "model": None,
        "copyright_safe": True,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Metric validation
# ──────────────────────────────────────────────────────────────────────────────
def validate_metric(draft: dict[str, Any], brief: dict[str, Any]) -> dict[str, Any]:
    """Compare the melody-aligned section's lines to the per-line syllable targets."""
    language = draft.get("language") or brief.get("language") or "en"
    targets = brief["metric"].get("line_syllable_targets") or []
    sections = draft.get("sections") or []
    # The first 'verse' is the melody-aligned section by convention.
    verse = next((s for s in sections if s.get("type") == "verse"), sections[0] if sections else {"lines": []})
    rows = []
    mismatches = 0
    for i, line in enumerate(verse.get("lines", [])):
        actual = _count_line_syllables(line, language)
        target = targets[i] if i < len(targets) else None
        fit = None
        if target is not None:
            fit = abs(actual - target) <= 1
            if not fit:
                mismatches += 1
        rows.append({"line": line, "actual_syllables": actual, "target_syllables": target, "fit": fit})
    aligned = bool(targets)
    return {
        "melody_aligned": aligned,
        "n_target_lines": len(targets),
        "n_generated_lines": len(verse.get("lines", [])),
        "rows": rows,
        "mismatches": mismatches,
        "fit_ratio": round(1 - mismatches / max(1, len([r for r in rows if r["target_syllables"] is not None])), 2)
        if aligned else None,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Orchestration
# ──────────────────────────────────────────────────────────────────────────────
def compose_draft(
    provider: Any,
    brief: dict[str, Any],
    existing_lyrics: str = "",
    mode: str = "generate",
    temperature: float = 0.85,
    tighten: bool = True,
) -> dict[str, Any]:
    """Generate a draft via the LLM provider, with metric validation.

    `mode` is 'generate' (from brief) or 'rewrite' (improve existing lyrics).
    Falls back to a heuristic draft if the provider is not live or fails.
    """
    if not getattr(provider, "is_live", False):
        draft = _heuristic_draft(brief)
        draft["metric_report"] = validate_metric(draft, brief)
        return draft

    prompt = _user_prompt(brief, existing_lyrics, mode)
    try:
        raw = provider.generate(prompt, system=_SYSTEM_PROMPT, max_tokens=900, temperature=temperature)
        parsed = _parse_json_draft(raw)
    except Exception as exc:  # noqa: BLE001
        draft = _heuristic_draft(brief)
        draft["notes"] = f"LLM call failed ({exc}); using heuristic fallback."
        draft["metric_report"] = validate_metric(draft, brief)
        return draft

    if not parsed or not parsed.get("sections"):
        draft = _heuristic_draft(brief)
        draft["notes"] = "LLM returned unparseable output; using heuristic fallback."
        draft["metric_report"] = validate_metric(draft, brief)
        return draft

    draft = {
        "title": parsed.get("title", "Untitled Draft"),
        "language": parsed.get("language", brief["language"]),
        "sections": parsed.get("sections", []),
        "notes": parsed.get("notes", ""),
        "source": getattr(provider, "name", "openai"),
        "model": getattr(provider, "model", None),
        "copyright_safe": True,
    }
    report = validate_metric(draft, brief)

    # Corrective pass whenever ANY line misses the metric by more than ±1.
    if tighten and report["melody_aligned"] and report["mismatches"] >= 1:
        fix_prompt = (
            _user_prompt(brief, existing_lyrics, mode)
            + "\n\nPREVIOUS ATTEMPT had these per-line syllable mismatches "
            "(line | got | needed):\n"
            + "\n".join(
                f"- {r['line']} | {r['actual_syllables']} | {r['target_syllables']}"
                for r in report["rows"] if r["target_syllables"] is not None and not r["fit"]
            )
            + "\n\nRewrite ONLY to fix the syllable counts (±1), keeping meaning and tone. "
            "Return the full JSON object again."
        )
        try:
            raw2 = provider.generate(fix_prompt, system=_SYSTEM_PROMPT, max_tokens=900, temperature=0.5)
            parsed2 = _parse_json_draft(raw2)
            if parsed2 and parsed2.get("sections"):
                draft2 = {
                    "title": parsed2.get("title", draft["title"]),
                    "language": parsed2.get("language", draft["language"]),
                    "sections": parsed2.get("sections", []),
                    "notes": parsed2.get("notes", draft["notes"]),
                    "source": draft["source"],
                    "model": draft["model"],
                    "copyright_safe": True,
                }
                report2 = validate_metric(draft2, brief)
                if report2["mismatches"] <= report["mismatches"]:
                    draft2["metric_report"] = report2
                    draft2["tightened"] = True
                    return draft2
        except Exception:  # noqa: BLE001
            pass

    draft["metric_report"] = report
    return draft


def regenerate_section(
    provider: Any,
    brief: dict[str, Any],
    section_type: str,
    temperature: float = 0.9,
) -> dict[str, Any]:
    """Regenerate a single section (verse/chorus/bridge), respecting metric for verses."""
    metric = brief["metric"]
    intent = brief["intent"]
    lang = brief["language"]
    constraints = []
    if section_type == "verse" and metric.get("has_vocal_midi"):
        targets = metric["line_syllable_targets"]
        constraints.append(f"Produce exactly {len(targets)} lines with syllable counts {targets} (±1), in order.")
    else:
        constraints.append("Produce 2–4 singable lines.")

    if not getattr(provider, "is_live", False):
        images = (intent.get("promising_images") or []) + (intent.get("lexical_fields") or ["light"])
        n = len(metric.get("line_syllable_targets") or []) if section_type == "verse" else 3
        return {"type": section_type, "lines": [f"[draft] {images[i % len(images)]}" for i in range(max(2, n))]}

    prompt = (
        f"Write ONLY the {section_type} of an original song in language {lang}.\n"
        f"Theme: {intent.get('core_theme')}; temperature: {intent.get('emotional_temperature')}.\n"
        f"Lexical fields: {', '.join(intent.get('lexical_fields', [])[:6])}.\n"
        f"Avoid clichés: {', '.join(intent.get('images_to_avoid', [])[:4])}.\n"
        + " ".join(constraints)
        + '\nReturn STRICT JSON: {"type": "' + section_type + '", "lines": [str, ...]}. JSON only.'
    )
    try:
        raw = provider.generate(prompt, system=_SYSTEM_PROMPT, max_tokens=400, temperature=temperature)
        parsed = _parse_json_draft(raw)
        if parsed and parsed.get("lines"):
            return {"type": section_type, "lines": parsed["lines"]}
    except Exception:  # noqa: BLE001
        pass
    return {"type": section_type, "lines": [f"[draft] {section_type} (regeneration failed)"]}


def draft_to_text(draft: dict[str, Any]) -> str:
    """Flatten a structured draft into editable plain lyrics text."""
    out: list[str] = []
    title = draft.get("title")
    if title:
        out.append(f"# {title}")
        out.append("")
    for sec in draft.get("sections", []):
        label = (sec.get("type") or "section").title()
        out.append(f"[{label}]")
        out.extend(sec.get("lines", []))
        out.append("")
    return "\n".join(out).strip()
