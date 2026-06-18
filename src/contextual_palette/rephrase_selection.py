"""On-demand rephrasing of a selected lyric line/block.

Called only when the user clicks "Rephrase". Uses the configured LLM provider
(OpenAI) when live, with a safe heuristic fallback. The reference artist is used
ONLY as abstract direction (themes/moods/stance) — never imitated, quoted, or
paraphrased — and no copyrighted lyrics are ever produced or stored.
"""
from __future__ import annotations

import re
from typing import Any

from .modules.metric_fit import _estimate_syllables


_SYSTEM_PROMPT = (
    "You are a melody-aware lyric editor. You rewrite ONLY the selected line or "
    "block the user gives you. Hard rules:\n"
    "- Write 100% original lyrics. Never copy, quote, or paraphrase any existing "
    "song or artist. Never reproduce copyrighted text.\n"
    "- Rewrite only the provided selection; do NOT write a whole song.\n"
    "- CRITICAL: do NOT return the original words merely re-split or re-grouped "
    "into different lines. You must actually CHANGE THE WORDING (compress, expand, "
    "or swap words) so each line lands on its target syllable count.\n"
    "- Each output line must hit its PER-LINE syllable target (the prompt lists the "
    "target and the syllables to add/cut for every line). Count syllables carefully "
    "before answering.\n"
    "- The targets can be DRASTICALLY different between lines (e.g. line 1 = 2 "
    "syllables, line 2 = 3, line 3 = 12). This is intentional and follows the melody. "
    "NEVER even out the lines to a similar length — a 2-syllable line must stay tiny "
    "(e.g. \"Kids draw.\") and a 12-syllable line must be long and full.\n"
    "- Preserve the core image/meaning of each line and keep the final rhyme word "
    "where possible, but reword the rest freely to fit the melody.\n"
    "- Respect the requested mood direction and rhyme structure.\n"
    "- Use any reference direction ONLY as abstract guidance (themes, mood, imagery "
    "density, narrative stance). Never imitate or echo the artist.\n"
    "- Keep the same number of lines as the input selection.\n"
    "- Return ONLY the rewritten line/block as plain text, no commentary, no labels."
)

# How aggressively to chase the melodic metric.
_STRENGTH_INSTRUCTIONS = {
    "loose (keep my words)": (
        "METRIC PRIORITY: LOW. Preserve the writer's exact wording and meaning as much "
        "as possible. Only adjust a line if it is off its target by 3 or more syllables."
    ),
    "balanced": (
        "METRIC PRIORITY: MEDIUM. Reword each line as needed to bring it within ±1 of its "
        "target syllable count, while preserving the core meaning and the rhyme word."
    ),
    "tight (rewrite to fit melody)": (
        "METRIC PRIORITY: HIGH. Hitting each line's target syllable count (±1) is more "
        "important than keeping the original wording. Rewrite aggressively — compress or "
        "expand, swap words and phrasing — but keep the core image and the final rhyme word."
    ),
}
_DEFAULT_STRENGTH = "balanced"


def _reference_direction(context: dict[str, Any], artist: str | None) -> dict[str, Any]:
    ref = context.get("reference_profile") or {}
    patterns = ref.get("abstract_patterns", {}) if isinstance(ref, dict) else {}
    direction = {
        "source": ref.get("source") or "none",
        "themes": (patterns.get("common_themes") or [])[:6],
        "moods": (patterns.get("dominant_moods") or patterns.get("moods") or [])[:6],
        "narrative_stance": patterns.get("narrative_stance"),
        "imagery_density": patterns.get("imagery_density"),
        "symbolic_register": (patterns.get("symbolic_register") or [])[:6],
    }
    return {k: v for k, v in direction.items() if v}


def _singable_line_indices(full_lyrics: str) -> list[int]:
    """Raw line indices of actual sung lines (skip blanks and [..]/# headers)."""
    out: list[int] = []
    for i, l in enumerate((full_lyrics or "").splitlines()):
        s = l.strip()
        if s and not re.match(r"^[\[#]", s):
            out.append(i)
    return out


def midi_phrase_slots(vocal_midi: dict[str, Any] | None) -> list[int]:
    """Syllable slots per detected MIDI phrase, in order."""
    phrases = (vocal_midi or {}).get("phrase_estimates") or []
    return [int(p["syllable_slots"]) for p in phrases
            if isinstance(p, dict) and p.get("syllable_slots") is not None]


def compute_line_targets(selected_text: str, context: dict[str, Any],
                         fallback_per_line: int | None = None) -> list[dict[str, Any]]:
    """Map EACH selected line to its corresponding vocal-MIDI phrase, in order.

    The k-th sung line of the song is matched to the k-th MIDI phrase, so if the
    first phrase has 2 notes the first line's target is ~2 syllables (true
    melody-aware mapping). When the selection starts mid-song we use its global
    position among sung lines (from ``selection_line_range``). If MIDI is absent
    we fall back to ``fallback_per_line``.
    """
    lines = [l for l in selected_text.splitlines() if l.strip()] or [selected_text]
    midi = midi_phrase_slots(context.get("vocal_midi"))
    singable = _singable_line_indices(context.get("full_lyrics", ""))
    idxs = context.get("selection_line_idxs")
    rng = context.get("selection_line_range")

    def _ordinal(raw_idx: int) -> int:
        # 0-based position of this raw line among all sung lines => MIDI phrase index.
        return sum(1 for s in singable if s < raw_idx)

    out: list[dict[str, Any]] = []
    for j, ln in enumerate(lines):
        if idxs and j < len(idxs):
            k = _ordinal(idxs[j])
        elif rng and singable:
            k = _ordinal(rng[0]) + j
        else:
            k = j
        if midi:
            tgt = midi[k] if k < len(midi) else midi[-1]
        else:
            tgt = fallback_per_line
        cur = _estimate_syllables(ln)
        out.append({"line": ln, "current": cur, "target": tgt,
                    "delta": (cur - tgt) if tgt is not None else None})
    return out


def _per_line_targets(selected_text: str, audit: dict[str, Any],
                      context: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-line targets: true MIDI phrase mapping, heuristic fallback otherwise."""
    lines = [l for l in selected_text.splitlines() if l.strip()] or [selected_text]
    n = len(lines)
    rng = (audit.get("metric") or {}).get("target_syllable_range")
    fb = max(2, round(((rng[0] + rng[1]) / 2) / n)) if (rng and len(rng) == 2) else None
    return compute_line_targets(selected_text, context, fallback_per_line=fb)


def _mismatches(report: dict[str, Any]) -> int:
    return sum(1 for r in report.get("per_line", [])
               if r.get("target") is not None and not r.get("fit"))


def _corrective_prompt(prev_candidate: str, report: dict[str, Any]) -> str:
    """Ask the model to fix ONLY the lines that missed their syllable target."""
    blocks = ["Your previous attempt did not hit every per-line syllable target.",
              "PREVIOUS ATTEMPT:", prev_candidate, "",
              "Fix it. Each line MUST have exactly the target syllable count below. "
              "Keep the lines that are already correct; rewrite the others — change "
              "the wording, do not just re-split. Short targets must stay very short."]
    blocks.append("")
    for i, r in enumerate(report.get("per_line", []), 1):
        tgt = r.get("target")
        if tgt is None:
            blocks.append(f"  Line {i}: \"{r['text']}\" — keep (no target)")
        elif r.get("fit"):
            blocks.append(f"  Line {i}: \"{r['text']}\" — OK ({r['syllables']}≈{tgt})")
        else:
            d = r["syllables"] - tgt
            verb = f"CUT {d}" if d > 0 else f"ADD {-d}"
            blocks.append(f"  Line {i}: \"{r['text']}\" = {r['syllables']} syllables → "
                          f"MUST be {tgt} ({verb} syllables)")
    blocks.append("")
    blocks.append("Return ONLY the corrected lines, same number of lines, plain text.")
    return "\n".join(blocks)


def _metric_report(candidate: str, per_line_in: list[dict[str, Any]]) -> dict[str, Any]:
    lines = [l for l in candidate.splitlines() if l.strip()] or [candidate]
    rows = []
    in_range = True
    for i, ln in enumerate(lines):
        tgt = per_line_in[i]["target"] if i < len(per_line_in) else None
        syl = _estimate_syllables(ln)
        fit = (tgt is None) or (abs(syl - tgt) <= 1)
        if tgt is not None and not fit:
            in_range = False
        rows.append({"text": ln, "syllables": syl, "target": tgt, "fit": fit})
    targets = [r["target"] for r in rows if r["target"] is not None]
    return {
        "per_line": rows,
        "target_syllable_range": ([min(targets), max(targets)] if targets else None),
        "all_in_range": in_range if targets else None,
    }


def _user_prompt(selected_text, audit, context, mood_target, rhyme_structure,
                 metric_strength, ref_dir, per_line) -> str:
    metric = audit.get("metric", {})
    blocks = ["SELECTION TO REWRITE:", selected_text, ""]

    blocks.append("AUDIT FINDINGS:")
    blocks.append(f"- summary: {audit.get('summary_blurb', '')}")
    for item in (audit.get("diagnosis", {}).get("what_does_not_work") or [])[:4]:
        blocks.append(f"- issue: {item}")
    for item in (audit.get("diagnosis", {}).get("recommended_action") or [])[:3]:
        blocks.append(f"- action: {item}")
    blocks.append("")

    blocks.append(f"MELODY METRIC (mode: {metric.get('mode', 'heuristic')}):")
    blocks.append(_STRENGTH_INSTRUCTIONS.get(metric_strength, _STRENGTH_INSTRUCTIONS[_DEFAULT_STRENGTH]))
    _tgts = [pl["target"] for pl in per_line if pl["target"] is not None]
    if _tgts and (max(_tgts) - min(_tgts)) >= 4:
        blocks.append(f"NOTE: targets vary a lot (from {min(_tgts)} to {max(_tgts)} syllables). "
                      "Keep that contrast — short lines must be very short, long lines long.")
    blocks.append("PER-LINE TARGETS (each output line MUST have exactly this many syllables):")
    for i, pl in enumerate(per_line, 1):
        tgt = pl["target"]
        if tgt is None:
            blocks.append(f"  Line {i}: \"{pl['line']}\" — now {pl['current']} syllables (no MIDI target)")
        else:
            d = pl["current"] - tgt
            action = "ok" if abs(d) <= 1 else (f"cut ~{d}" if d > 0 else f"add ~{-d}")
            blocks.append(f"  Line {i}: target = {tgt} syllables ({action}) "
                          f"— from \"{pl['line']}\" (now {pl['current']})")
    blocks.append("")

    blocks.append(f"MOOD DIRECTION: {mood_target}")
    blocks.append(f"RHYME STRUCTURE: {rhyme_structure}")
    blocks.append("")

    if ref_dir:
        blocks.append("REFERENCE DIRECTION (abstract only — do NOT imitate or quote):")
        for k, v in ref_dir.items():
            if k == "source":
                continue
            blocks.append(f"- {k}: {v}")
        blocks.append("")

    blocks.append("Return ONLY the rewritten line/block — same number of lines, plain text, "
                  "actually reworded to hit the targets above (not the original lines re-split).")
    return "\n".join(blocks)


def _heuristic_rephrase(selected_text: str, per_line: list[dict[str, Any]]) -> str:
    """Best-effort offline rephrase: trims fillers per line toward the target.

    This never invents new copyrighted text; it lightly edits the user's own line.
    """
    fillers = {"just", "really", "very", "so", "that", "then", "now", "oh", "yeah",
               "proprio", "davvero", "molto", "così", "poi", "ora"}
    out_lines = []
    for pl in per_line:
        words = pl["line"].split()
        tgt = pl["target"]
        if tgt is not None:
            while _estimate_syllables(" ".join(words)) > tgt + 1 and any(
                w.lower().strip(",.!?;:") in fillers for w in words
            ):
                for i, w in enumerate(words):
                    if w.lower().strip(",.!?;:") in fillers:
                        words.pop(i)
                        break
                else:
                    break
        out_lines.append(" ".join(words))
    return "\n".join(out_lines)


def rephrase_selection(
    selected_text: str,
    audit: dict[str, Any],
    context: dict[str, Any],
    mood_target: str = "balanced",
    rhyme_structure: str = "alternating (ABAB)",
    active_reference_artist: str | None = None,
    metric_strength: str = _DEFAULT_STRENGTH,
    provider: Any = None,
) -> dict[str, Any]:
    selected_text = (selected_text or "").strip()
    ref_dir = _reference_direction(context, active_reference_artist)
    per_line = _per_line_targets(selected_text, audit, context)
    has_targets = any(pl["target"] is not None for pl in per_line)

    explanation = {
        "metric": (f"{metric_strength} · per-line syllable targets "
                   f"{[pl['target'] for pl in per_line]}" if has_targets
                   else "No vocal MIDI — used a heuristic phrase length."),
        "mood": f"Steered toward: {mood_target}.",
        "rhyme": f"Aimed for: {rhyme_structure}.",
        "reference": (f"Abstract direction from {ref_dir.get('source')}"
                      + (f" (artist focus: {active_reference_artist})" if active_reference_artist
                         and active_reference_artist != "No specific artist" else "")
                      + "." if ref_dir else "No reference direction applied."),
        "safety": "Original text only — no copyrighted lyrics, quotes, or imitation.",
    }

    if provider is not None and getattr(provider, "is_live", False) and selected_text:
        try:
            # How many corrective passes to allow when lines miss their target.
            max_passes = (3 if metric_strength.startswith("tight")
                          else 2 if metric_strength == _DEFAULT_STRENGTH else 1)
            prompt = _user_prompt(selected_text, audit, context, mood_target,
                                  rhyme_structure, metric_strength, ref_dir, per_line)
            # Higher temperature when chasing the metric hard, to escape the original phrasing.
            temp = 0.95 if metric_strength.startswith("tight") else 0.85

            best_candidate: str | None = None
            best_report: dict[str, Any] = {}
            best_miss = 10**9
            for attempt in range(max_passes):
                raw = provider.generate(prompt, system=_SYSTEM_PROMPT,
                                        max_tokens=400, temperature=temp)
                candidate = _clean_candidate(raw, selected_text)
                if not candidate:
                    break
                report = _metric_report(candidate, per_line)
                miss = _mismatches(report)
                if miss < best_miss:
                    best_miss, best_candidate, best_report = miss, candidate, report
                if miss == 0 or not has_targets:
                    break
                # Corrective re-pass: focus the model on the lines still off-target.
                prompt = _corrective_prompt(candidate, report)
                temp = max(0.4, temp - 0.25)

            if best_candidate:
                explanation["metric"] += f" · {best_miss} line(s) off-target after {attempt + 1} pass(es)."
                return {
                    "candidate": best_candidate,
                    "explanation": explanation,
                    "metric_report": best_report,
                    "source": "openai",
                    "copyright_safe": True,
                }
        except Exception as exc:  # noqa: BLE001 - never crash on LLM/network/quota
            explanation["safety"] += f" (Live LLM unavailable: {type(exc).__name__}; used heuristic fallback.)"

    candidate = _heuristic_rephrase(selected_text, per_line)
    source = "openai_fallback_heuristic" if (provider is not None and getattr(provider, "is_live", False)) else "mock"
    return {
        "candidate": candidate,
        "explanation": explanation,
        "metric_report": _metric_report(candidate, per_line),
        "source": source,
        "copyright_safe": True,
    }


def _clean_candidate(raw: str, selected_text: str) -> str:
    """Strip code fences/labels and clamp to the selection's line count."""
    text = (raw or "").strip()
    text = re.sub(r"^```[a-zA-Z]*\n?|```$", "", text).strip()
    # Drop obvious section labels the model might add.
    cleaned = []
    for line in text.splitlines():
        s = line.strip()
        if re.match(r"^[\[(]?(verse|chorus|bridge|intro|outro|hook)\b", s, re.I):
            continue
        cleaned.append(line)
    text = "\n".join(cleaned).strip()
    n_in = len([l for l in selected_text.splitlines() if l.strip()]) or 1
    out_lines = [l for l in text.splitlines() if l.strip()]
    if out_lines and len(out_lines) > n_in:
        out_lines = out_lines[:n_in]
    return "\n".join(out_lines).strip()
