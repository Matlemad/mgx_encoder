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
    "- Preserve the user's meaning unless the audit explicitly asks for compression.\n"
    "- Respect the syllable target so the words fit the melody.\n"
    "- Respect the requested mood direction and rhyme structure.\n"
    "- Use any reference direction ONLY as abstract guidance (themes, mood, "
    "imagery density, narrative stance). Never imitate or echo the artist.\n"
    "- Keep the same number of lines as the input selection.\n"
    "- Return ONLY the rewritten line/block as plain text, no commentary, no labels."
)


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


def _metric_report(candidate: str, audit: dict[str, Any]) -> dict[str, Any]:
    target = (audit.get("metric") or {}).get("target_syllable_range")
    lines = [l for l in candidate.splitlines() if l.strip()] or [candidate]
    per_line = [{"text": l, "syllables": _estimate_syllables(l)} for l in lines]
    report: dict[str, Any] = {"per_line": per_line, "target_syllable_range": target}
    if target and len(target) == 2:
        lo, hi = target
        report["all_in_range"] = all(lo - 1 <= p["syllables"] <= hi + 1 for p in per_line)
    return report


def _user_prompt(selected_text, audit, context, mood_target, rhyme_structure, ref_dir) -> str:
    metric = audit.get("metric", {})
    target = metric.get("target_syllable_range")
    blocks = ["SELECTION TO REWRITE:", selected_text, ""]

    blocks.append("AUDIT FINDINGS:")
    blocks.append(f"- summary: {audit.get('summary_blurb', '')}")
    for item in (audit.get("diagnosis", {}).get("what_does_not_work") or [])[:4]:
        blocks.append(f"- issue: {item}")
    for item in (audit.get("diagnosis", {}).get("recommended_action") or [])[:4]:
        blocks.append(f"- action: {item}")
    blocks.append("")

    blocks.append("MELODY METRIC:")
    blocks.append(f"- mode: {metric.get('mode', 'heuristic')}")
    if target:
        blocks.append(f"- keep each line within {target[0]}-{target[1]} syllables")
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

    blocks.append("Return ONLY the rewritten line/block, same number of lines, plain text.")
    return "\n".join(blocks)


def _heuristic_rephrase(selected_text: str, audit: dict[str, Any]) -> str:
    """Best-effort offline rephrase: light cliché swaps and trimming hints.

    This never invents new copyrighted text; it lightly edits the user's own line.
    """
    text = selected_text
    metric = audit.get("metric", {})
    target = metric.get("target_syllable_range")
    # Trim trailing filler words if over the syllable budget.
    fillers = {"just", "really", "very", "so", "that", "then", "now", "oh", "yeah",
               "proprio", "davvero", "molto", "così", "poi", "ora"}
    if target and len(target) == 2:
        hi = target[1]
        lines = text.splitlines() or [text]
        out_lines = []
        for line in lines:
            words = line.split()
            while _estimate_syllables(" ".join(words)) > hi + 1 and any(
                w.lower().strip(",.!?;:") in fillers for w in words
            ):
                for i, w in enumerate(words):
                    if w.lower().strip(",.!?;:") in fillers:
                        words.pop(i)
                        break
                else:
                    break
            out_lines.append(" ".join(words))
        text = "\n".join(out_lines)
    return text


def rephrase_selection(
    selected_text: str,
    audit: dict[str, Any],
    context: dict[str, Any],
    mood_target: str = "balanced",
    rhyme_structure: str = "alternating (ABAB)",
    active_reference_artist: str | None = None,
    provider: Any = None,
) -> dict[str, Any]:
    selected_text = (selected_text or "").strip()
    ref_dir = _reference_direction(context, active_reference_artist)

    explanation = {
        "metric": "Targeted the melodic syllable window." if (audit.get("metric") or {}).get("target_syllable_range")
        else "No vocal MIDI — used a heuristic phrase length.",
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
            prompt = _user_prompt(selected_text, audit, context, mood_target, rhyme_structure, ref_dir)
            raw = provider.generate(prompt, system=_SYSTEM_PROMPT, max_tokens=400, temperature=0.85)
            candidate = _clean_candidate(raw, selected_text)
            if candidate:
                return {
                    "candidate": candidate,
                    "explanation": explanation,
                    "metric_report": _metric_report(candidate, audit),
                    "source": "openai",
                    "copyright_safe": True,
                }
        except Exception as exc:  # noqa: BLE001 - never crash on LLM/network/quota
            explanation["safety"] += f" (Live LLM unavailable: {type(exc).__name__}; used heuristic fallback.)"

    candidate = _heuristic_rephrase(selected_text, audit)
    source = "openai_fallback_heuristic" if (provider is not None and getattr(provider, "is_live", False)) else "mock"
    return {
        "candidate": candidate,
        "explanation": explanation,
        "metric_report": _metric_report(candidate, audit),
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
