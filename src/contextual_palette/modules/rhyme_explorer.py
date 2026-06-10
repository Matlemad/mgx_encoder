"""Module 2: Rhyme Explorer — find rhymes, assonances, consonances."""
from __future__ import annotations
from typing import Any
from ..selection_analyzer import SelectionType

id = "rhyme_explorer"
title = "Rhyme Explorer"
supported_types = [SelectionType.WORD, SelectionType.PHRASE]


def _get_ending(word: str, n: int = 3) -> str:
    return word[-n:] if len(word) >= n else word


def _vowels_of(word: str) -> str:
    return "".join(c for c in word.lower() if c in "aeiou")


def _consonants_of(word: str) -> str:
    return "".join(c for c in word.lower() if c.isalpha() and c not in "aeiou")


_RHYME_BANK_IT = {
    "ore": ["amore", "dolore", "cuore", "fiore", "colore", "errore", "splendore", "calore", "vapore"],
    "ento": ["vento", "momento", "lamento", "sentimento", "tormento", "argento", "accento"],
    "are": ["mare", "andare", "tornare", "restare", "sognare", "volare", "parlare", "camminare"],
    "ino": ["cammino", "mattino", "destino", "vicino", "bambino", "giardino", "divino"],
    "ato": ["passato", "amato", "stato", "nato", "creato", "cercato", "trovato"],
    "one": ["emozione", "canzone", "ragione", "passione", "stazione", "visione"],
    "ita": ["vita", "ferita", "partita", "salita", "infinita", "smarrita"],
    "ente": ["mente", "gente", "presente", "corrente", "ardente", "silente"],
}
_RHYME_BANK_EN = {
    "ight": ["night", "light", "sight", "flight", "right", "bright", "fight", "height"],
    "ove": ["love", "above", "dove", "shove", "glove"],
    "ain": ["rain", "pain", "train", "chain", "remain", "explain", "brain", "vain"],
    "eart": ["heart", "start", "part", "art", "apart", "chart"],
    "ound": ["sound", "ground", "found", "around", "bound", "wound", "round"],
    "ire": ["fire", "desire", "wire", "higher", "tire", "inspire"],
    "ream": ["dream", "stream", "beam", "seem", "gleam", "team"],
    "one": ["alone", "stone", "bone", "phone", "tone", "zone", "known"],
}


def run(text: str, context: dict[str, Any]) -> dict[str, Any]:
    words = text.strip().lower().split()
    target = words[-1] if words else ""
    if not target:
        return {"perfect_rhymes": [], "near_rhymes": [], "assonances": [], "consonances": []}

    ending2 = _get_ending(target, 2)
    ending3 = _get_ending(target, 3)
    ending4 = _get_ending(target, 4)
    target_vowels = _vowels_of(target)
    target_consonants = _consonants_of(target)

    perfect = []
    near = []
    for bank in [_RHYME_BANK_IT, _RHYME_BANK_EN]:
        for ending, words_list in bank.items():
            if target.endswith(ending):
                for w in words_list:
                    if w != target:
                        perfect.append(w)
            elif ending3 in ending or ending in ending3:
                for w in words_list:
                    if w != target:
                        near.append(w)

    if not perfect and not near:
        for bank in [_RHYME_BANK_IT, _RHYME_BANK_EN]:
            for ending, words_list in bank.items():
                if ending2 == ending[-2:]:
                    near.extend(w for w in words_list if w != target)

    assonances = []
    consonances = []
    for bank in [_RHYME_BANK_IT, _RHYME_BANK_EN]:
        for _, words_list in bank.items():
            for w in words_list:
                if w == target:
                    continue
                if _vowels_of(w)[-2:] == target_vowels[-2:] and w not in perfect and w not in near:
                    assonances.append(w)
                if _consonants_of(w)[-2:] == target_consonants[-2:] and w not in perfect and w not in near:
                    consonances.append(w)

    return {
        "perfect_rhymes": list(dict.fromkeys(perfect))[:10],
        "near_rhymes": list(dict.fromkeys(near))[:10],
        "assonances": list(dict.fromkeys(assonances))[:8],
        "consonances": list(dict.fromkeys(consonances))[:8],
    }
