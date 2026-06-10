"""Run palette modules by selection type and build context."""
from __future__ import annotations
from typing import Any
from .selection_analyzer import SelectionType, classify_selection
from .modules import (
    lexical_constellation,
    rhyme_explorer,
    metric_rewrite,
    emotional_reading,
    corpus_insights,
    cliche_detector,
    imagery_analyzer,
    narrative_function,
    repetition_radar,
    inspiration_directions,
)

_ALL_MODULES = [
    lexical_constellation,
    rhyme_explorer,
    metric_rewrite,
    emotional_reading,
    corpus_insights,
    cliche_detector,
    imagery_analyzer,
    narrative_function,
    repetition_radar,
    inspiration_directions,
]


def get_available_modules(sel_type: SelectionType) -> list:
    return [m for m in _ALL_MODULES if sel_type in m.supported_types]


def run_module(module, text: str, context: dict[str, Any]) -> dict[str, Any]:
    """Safely run a single module."""
    try:
        return module.run(text, context)
    except Exception as e:
        return {"error": str(e)}


def run_all_for_selection(
    text: str,
    full_lyrics: str = "",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify selection, run all applicable modules, return results."""
    if context is None:
        context = {}
    sel_type = classify_selection(text, full_lyrics)
    modules = get_available_modules(sel_type)

    results = {"_selection_type": sel_type.value, "_selected_text": text[:200]}
    for m in modules:
        results[m.id] = run_module(m, text, context)

    # Cross-module context enrichment
    if "imagery_analyzer" in results:
        context["imagery"] = results["imagery_analyzer"]
    if "cliche_detector" in results:
        context["cliche"] = results["cliche_detector"]
    if inspiration_directions in modules:
        results[inspiration_directions.id] = run_module(inspiration_directions, text, context)

    return results
