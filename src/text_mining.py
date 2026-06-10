"""TACT-style text mining: tokenization, n-grams, co-occurrence, KWIC."""
from __future__ import annotations

import re
import string
from collections import Counter, defaultdict
from typing import Any

_EN_STOPWORDS = frozenset(
    "i me my myself we our ours ourselves you your yours yourself yourselves "
    "he him his himself she her hers herself it its itself they them their theirs "
    "themselves what which who whom this that these those am is are was were be "
    "been being have has had having do does did doing a an the and but if or "
    "because as until while of at by for with about against between through "
    "during before after above below to from up down in out on off over under "
    "again further then once here there when where why how all both each few "
    "more most other some such no nor not only own same so than too very s t "
    "can will just don should now d ll m o re ve y ain aren couldn didn doesn "
    "hadn hasn haven isn ma mightn mustn needn shan shouldn wasn weren won wouldn "
    "also still even much already yet".split()
)

_IT_STOPWORDS = frozenset(
    "il lo la le gli i un uno una di del dello della dei degli delle a al allo "
    "alla alle agli da dal dallo dalla dalle dagli in nel nello nella nelle nei "
    "negli con col su sul sullo sulla sulle sui sugli per tra fra e o ma che "
    "non si no mi ti ci vi ne lo la li le me te se ce ve ne io tu lui lei noi "
    "voi loro questo questa questi queste quello quella quelli quelle chi cui "
    "come dove quando quanto perche anche solo ancora gia piu poi se sono ha ho "
    "era sei suo sua suoi sue del della delle dei degli al alla alle agli dal "
    "dalla dalle dagli nel nella nelle nei negli sul sulla sulle sui sugli "
    "essere avere fare dire stare molto tutto ogni altro cosa".split()
)

STOPWORDS = _EN_STOPWORDS | _IT_STOPWORDS


def tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split into tokens."""
    text = text.lower()
    text = text.translate(str.maketrans("", "", string.punctuation))
    return [t for t in text.split() if t]


def remove_stopwords(tokens: list[str]) -> list[str]:
    return [t for t in tokens if t not in STOPWORDS]


def word_frequency(tokens: list[str]) -> dict[str, int]:
    return dict(Counter(tokens).most_common())


def ngram_frequency(tokens: list[str], n: int) -> dict[str, int]:
    if len(tokens) < n:
        return {}
    ngrams = [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]
    return dict(Counter(ngrams).most_common())


def cooccurrence(tokens: list[str], window: int = 5) -> dict[str, int]:
    """Co-occurrence counts within a sliding window."""
    pairs: Counter[str, int] = Counter()
    for i, tok in enumerate(tokens):
        for j in range(i + 1, min(i + window + 1, len(tokens))):
            pair = tuple(sorted([tok, tokens[j]]))
            pairs[f"{pair[0]} + {pair[1]}"] += 1
    return dict(pairs.most_common(100))


def kwic(tokens: list[str], keyword: str, context: int = 5) -> list[dict[str, str]]:
    """Keyword-in-context concordance."""
    keyword = keyword.lower()
    results = []
    for i, tok in enumerate(tokens):
        if tok == keyword:
            left = " ".join(tokens[max(0, i - context) : i])
            right = " ".join(tokens[i + 1 : i + context + 1])
            results.append({"left": left, "keyword": tok, "right": right})
    return results


def mine_text(text: str) -> dict[str, Any]:
    """Full text mining pipeline. Returns structured JSON-like result."""
    raw_tokens = tokenize(text)
    filtered = remove_stopwords(raw_tokens)

    return {
        "n_raw_tokens": len(raw_tokens),
        "n_filtered_tokens": len(filtered),
        "tokens": filtered[:500],
        "word_frequencies": word_frequency(filtered),
        "bigrams": ngram_frequency(filtered, 2),
        "trigrams": ngram_frequency(filtered, 3),
        "cooccurrences": cooccurrence(filtered),
        "kwic": {},
        "lexical_fields": [],
    }
