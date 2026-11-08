"""Búsqueda léxica en Python puro (modo SQLite): tokenización bilingüe español/inglés y puntuación BM25."""

import math
import re
import unicodedata
from typing import List, Sequence

BM25_K1 = 1.5
BM25_B = 0.75

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_VOWELS = "aeiou"

STOPWORDS = frozenset(
    # español
    "a al algo ante como con contra cual cuando de del desde donde e el ella ellos en entre era es esta este esto "
    "estos fue ha hay la las le les lo los mas me mi muy no nos o para pero por que se si sin sobre su sus te tu un "
    "una uno unos y ya "
    # inglés
    "an and are as at be been but by do does for from had has have how in is it its of on or that the their then "
    "there these this to was were what when where which who why will with".split()
)


def _fold_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _stem(word: str) -> str:
    """Stemming ligero para plurales y la 'e' final (es/en): ingresos→ingreso, controles→control, files→fil."""
    if len(word) > 4 and word.endswith("ies"):
        word = word[:-3] + "y"
    elif len(word) > 4 and word.endswith("es") and word[-3] not in _VOWELS:
        word = word[:-2]
    elif len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        word = word[:-1]
    if len(word) > 4 and word.endswith("e"):
        word = word[:-1]
    return word


def tokenize(text: str) -> List[str]:
    """Minúsculas, sin acentos, sin stopwords (es/en) y con stemming ligero."""
    if not text:
        return []
    folded = _fold_accents(text)
    return [_stem(tok) for tok in _TOKEN_RE.findall(folded) if tok not in STOPWORDS]


def bm25_scores(query_tokens: Sequence[str], documents: Sequence[Sequence[str]]) -> List[float]:
    """Puntuación Okapi BM25 de cada documento (lista de tokens) frente a la consulta."""
    n_docs = len(documents)
    if n_docs == 0 or not query_tokens:
        return [0.0] * n_docs

    avg_len = sum(len(d) for d in documents) / n_docs or 1.0
    doc_freq = {t: sum(1 for d in documents if t in d) for t in set(query_tokens)}

    scores: List[float] = []
    for doc in documents:
        score = 0.0
        length = len(doc)
        for term in set(query_tokens):
            tf = doc.count(term)
            if not tf:
                continue
            idf = math.log(1.0 + (n_docs - doc_freq[term] + 0.5) / (doc_freq[term] + 0.5))
            score += idf * tf * (BM25_K1 + 1.0) / (tf + BM25_K1 * (1.0 - BM25_B + BM25_B * length / avg_len))
        scores.append(score)
    return scores
