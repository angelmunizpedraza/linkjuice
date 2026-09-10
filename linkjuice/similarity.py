"""TF-IDF cosine similarity between pages. Pure Python, deterministic, no sklearn."""

from __future__ import annotations

import math
import re
from collections import Counter

from .crawl import Page

TOKEN = re.compile(r"[a-zá-úñü0-9][a-zá-úñü0-9'\-]{2,}", re.IGNORECASE)

# Small bilingual stop list: these dominate any Spanish or English corpus and
# would make every page look similar to every other page.
STOPWORDS = {
    # English
    "the", "and", "for", "you", "your", "with", "that", "this", "from", "are",
    "was", "were", "have", "has", "had", "not", "but", "can", "will", "our",
    "all", "any", "how", "what", "when", "who", "why", "his", "her", "its",
    "their", "they", "them", "there", "here", "more", "most", "than", "then",
    "also", "into", "out", "about", "over", "some", "such", "each", "other",
    # Spanish
    "que", "los", "las", "del", "una", "uno", "unos", "unas", "con", "por",
    "para", "como", "más", "pero", "sus", "les", "eso", "esta", "este", "estos",
    "estas", "son", "sin", "sobre", "entre", "cuando", "donde", "porque",
    "también", "muy", "todo", "toda", "todos", "todas", "hay", "ser", "está",
    "están", "hace", "puede", "pueden", "desde", "cada", "otro", "otra",
}


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN.findall(text) if t.lower() not in STOPWORDS]


def _tfidf(pages: list[Page]) -> tuple[list[dict[str, float]], dict[str, float]]:
    docs = [Counter(tokenize(f"{p.title} {p.h1} {p.text}")) for p in pages]
    n = len(docs) or 1
    df: Counter = Counter()
    for doc in docs:
        df.update(doc.keys())
    idf = {term: math.log((1 + n) / (1 + count)) + 1.0 for term, count in df.items()}

    vectors: list[dict[str, float]] = []
    for doc in docs:
        total = sum(doc.values()) or 1
        vec = {term: (count / total) * idf[term] for term, count in doc.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        vectors.append({term: v / norm for term, v in vec.items()})
    return vectors, idf


def similarity_matrix(pages: list[Page]) -> dict[tuple[str, str], float]:
    """Cosine similarity for every unordered pair, keyed both ways for easy lookup."""
    vectors, _ = _tfidf(pages)
    sims: dict[tuple[str, str], float] = {}
    for i, a in enumerate(pages):
        for j in range(i + 1, len(pages)):
            b = pages[j]
            va, vb = vectors[i], vectors[j]
            if len(vb) < len(va):
                va, vb = vb, va
            score = sum(w * vb.get(term, 0.0) for term, w in va.items())
            sims[(a.url, b.url)] = score
            sims[(b.url, a.url)] = score
    return sims


def top_terms(page: Page, pages: list[Page], k: int = 6) -> list[str]:
    """The terms that make this page distinctive — candidate anchor text."""
    vectors, _ = _tfidf(pages)
    index = {p.url: i for i, p in enumerate(pages)}
    vec = vectors[index[page.url]]
    ranked = sorted(vec.items(), key=lambda kv: (-kv[1], kv[0]))
    return [term for term, _ in ranked[:k]]
