"""Module 1: Lexical Constellation — expand semantic territory around selected text."""
from __future__ import annotations
from typing import Any
from ..selection_analyzer import SelectionType

id = "lexical_constellation"
title = "Lexical Constellation"
supported_types = [SelectionType.WORD, SelectionType.PHRASE]

_SEMANTIC_MAP = {
    "mare": ["vento", "sale", "orizzonte", "onda", "corrente", "porto", "approdo", "marea", "sabbia"],
    "sea": ["wind", "salt", "horizon", "wave", "current", "harbor", "shore", "tide", "sand"],
    "night": ["moon", "stars", "silence", "darkness", "dream", "shadow", "cold", "sleep", "sky"],
    "notte": ["luna", "stelle", "silenzio", "buio", "sogno", "ombra", "freddo", "sonno", "cielo"],
    "love": ["heart", "touch", "hold", "fire", "warmth", "devotion", "tenderness", "desire", "flame"],
    "amore": ["cuore", "tocco", "fuoco", "calore", "tenerezza", "desiderio", "fiamma", "abbraccio"],
    "pain": ["wound", "scar", "ache", "bleeding", "fracture", "silence", "absence", "weight"],
    "dolore": ["ferita", "cicatrice", "peso", "silenzio", "assenza", "frattura", "vuoto"],
    "road": ["dust", "horizon", "steps", "distance", "journey", "crossing", "destination", "path"],
    "strada": ["polvere", "orizzonte", "passi", "distanza", "viaggio", "incrocio", "meta", "sentiero"],
    "light": ["dawn", "ray", "glow", "shadow", "spark", "warmth", "beam", "flicker"],
    "luce": ["alba", "raggio", "bagliore", "ombra", "scintilla", "calore", "fascio", "riflesso"],
    "time": ["clock", "moment", "forever", "passing", "memory", "waiting", "return", "age"],
    "tempo": ["orologio", "momento", "eterno", "attesa", "memoria", "ritorno", "stagione"],
}


def run(text: str, context: dict[str, Any]) -> dict[str, Any]:
    word = text.strip().lower().split()[0] if text.strip() else ""
    local = _SEMANTIC_MAP.get(word, [])[:5]
    corpus = _SEMANTIC_MAP.get(word, [])[5:] if word in _SEMANTIC_MAP else []

    if not local:
        mining = context.get("mining", {})
        cooc = mining.get("cooccurrences", {})
        for pair, _ in list(cooc.items())[:10]:
            parts = pair.split(" + ")
            for p in parts:
                if p != word and p not in local:
                    local.append(p)
            if len(local) >= 5:
                break

    clusters = []
    if local:
        clusters.append({"label": "primary_field", "words": local[:4]})
    if corpus:
        clusters.append({"label": "extended_field", "words": corpus[:4]})

    return {"local_connections": local, "corpus_connections": corpus, "semantic_clusters": clusters}
