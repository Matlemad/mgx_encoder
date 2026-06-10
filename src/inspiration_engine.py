"""Inspiration engine: combines text mining, MGX, and provider data into creative directions."""
from __future__ import annotations

from typing import Any


def _extract_dominant_fields(mining: dict[str, Any]) -> list[str]:
    """Derive abstract lexical fields from word frequencies."""
    _FIELD_MAP = {
        "love": ["love", "heart", "kiss", "hold", "touch", "feel", "dear", "amore", "cuore"],
        "absence": ["gone", "away", "miss", "lost", "empty", "distance", "far", "lontano", "assenza"],
        "night": ["night", "moon", "dark", "star", "sleep", "dream", "notte", "luna", "stelle"],
        "movement": ["run", "walk", "dance", "road", "fly", "move", "step", "corri", "strada"],
        "nature": ["sun", "rain", "sea", "sky", "wind", "water", "tree", "sole", "mare", "cielo"],
        "time": ["time", "day", "year", "moment", "forever", "now", "wait", "tempo", "giorno"],
        "pain": ["pain", "cry", "tear", "hurt", "break", "wound", "blood", "dolore", "piangere"],
        "hope": ["hope", "light", "new", "rise", "tomorrow", "dawn", "believe", "speranza", "luce"],
    }
    words = set(mining.get("word_frequencies", {}).keys())
    fields = []
    for field, triggers in _FIELD_MAP.items():
        if words & set(triggers):
            fields.append(field)
    if not fields:
        fields = ["general"]
    return fields[:5]


def _music_lyrics_alignment(mgx: dict[str, Any] | None, fields: list[str]) -> str:
    """Generate a text insight about how the audio genome relates to the lyrics."""
    if not mgx:
        return "No audio genome available for alignment analysis."

    H = mgx.get("H", {})
    R = mgx.get("R", {})
    mode = H.get("key_mode", H.get("mode", "unknown"))
    bpm = R.get("bpm", 0)
    complexity = R.get("groove_complexity", 0)

    parts = []
    if "pain" in fields or "absence" in fields:
        if mode == "major":
            parts.append("The lyrics suggest melancholy but the audio genome is in a major key — this contrast could be intentional (bittersweet) or worth re-examining.")
        else:
            parts.append("Both lyrics and audio share a minor-key emotional gravity.")
    elif "hope" in fields or "love" in fields:
        if mode == "minor":
            parts.append("The lyrics express warmth but the audio genome sits in a minor key — consider whether this tension serves the song.")
        else:
            parts.append("Lyrics and audio align on an emotionally open, major-key character.")

    if bpm > 130:
        parts.append(f"High tempo ({bpm:.0f} BPM) suggests energy that may complement or contrast with lyrical themes.")
    elif bpm < 80:
        parts.append(f"Slow tempo ({bpm:.0f} BPM) supports contemplative or intimate lyrical space.")

    if complexity > 0.6:
        parts.append("High rhythmic complexity — lyrics could benefit from syncopated phrasing.")

    return " ".join(parts) if parts else "Audio and lyrics appear tonally compatible."


def _corpus_insights(musixmatch_data: dict[str, Any] | None, fields: list[str]) -> list[str]:
    """Generate corpus-level insights from the Musixmatch provider data."""
    if not musixmatch_data:
        return ["No corpus data available. Connect Musixmatch for real insights."]

    insights = []
    themes = musixmatch_data.get("themes", [])
    for t in themes:
        assoc = t.get("corpus_associations", [])
        if assoc:
            joined = ", ".join(assoc[:5])
            insights.append(f"In the reference corpus, '{t['theme']}' is often connected with: {joined}.")
    if not insights:
        for field in fields:
            insights.append(f"The lexical field '{field}' is present in your lyrics but no corpus data is available for deeper analysis.")
    return insights


def _writing_suggestions(fields: list[str], mining: dict[str, Any], cyanite_data: dict[str, Any] | None) -> list[str]:
    """Generate copyright-safe writing suggestions."""
    suggestions = []

    bigrams = mining.get("bigrams", {})
    top_bigrams = list(bigrams.keys())[:3]
    if top_bigrams:
        suggestions.append(f"Your most frequent word pairs are: {', '.join(top_bigrams)}. Consider varying these to avoid repetitive phrasing.")

    if "pain" in fields and "hope" not in fields:
        suggestions.append("The lyrics lean heavily into negative emotion. A single hopeful image could create powerful contrast.")
    if "movement" in fields:
        suggestions.append("Movement imagery is strong — try anchoring it with a specific destination or origin to give it narrative weight.")
    if "absence" in fields:
        suggestions.append("Absence is a central theme. Consider replacing direct statements ('I miss you') with spatial metaphors ('the empty chair').")
    if "night" in fields:
        suggestions.append("Night imagery dominates. A single reference to dawn or light could reframe the entire emotional arc.")

    if cyanite_data:
        mood = cyanite_data.get("mood_primary", "")
        if mood:
            suggestions.append(f"The audio mood reads as '{mood}' — ensure your lyrical tone supports or intentionally contrasts this.")

    if not suggestions:
        suggestions.append("Consider strengthening the chorus with a repeated symbolic object that anchors the emotional theme.")

    return suggestions


def generate_inspiration(
    mining: dict[str, Any],
    mgx: dict[str, Any] | None = None,
    cyanite_data: dict[str, Any] | None = None,
    musixmatch_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Combine all sources into creative direction insights."""
    fields = _extract_dominant_fields(mining)
    return {
        "dominant_lexical_fields": fields,
        "music_lyrics_alignment": _music_lyrics_alignment(mgx, fields),
        "reference_corpus_insights": _corpus_insights(musixmatch_data, fields),
        "writing_suggestions": _writing_suggestions(fields, mining, cyanite_data),
    }
