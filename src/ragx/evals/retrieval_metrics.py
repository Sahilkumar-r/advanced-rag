"""Page-level retrieval metrics (no LLM). Relevance is binary: a chunk is relevant if its page is expected.

Context recall and context precision need an LLM judge and land with the judge in phase 2.
"""
from __future__ import annotations

import math


def _rel(docs: list[str], expected: set[str], k: int) -> list[int]:
    return [1 if d in expected else 0 for d in docs[:k]]


def hit_at_k(docs: list[str], expected: set[str], k: int) -> float:
    """1 if any expected page is in the top k chunks (called hit@k in rag-demo)."""
    return float(any(_rel(docs, expected, k)))


def recall_at_k(docs: list[str], expected: set[str], k: int) -> float:
    """Share of expected pages found in the top k chunks."""
    return len(expected & set(docs[:k])) / len(expected)


def precision_at_k(docs: list[str], expected: set[str], k: int) -> float:
    """Share of the top k chunks whose page is expected. Divides by k even if fewer were returned."""
    return sum(_rel(docs, expected, k)) / k


def reciprocal_rank(docs: list[str], expected: set[str]) -> float:
    return next((1 / (i + 1) for i, d in enumerate(docs) if d in expected), 0.0)


def ndcg_at_k(docs: list[str], expected: set[str], k: int = 10) -> float:
    """Binary gain, earned once per page (first chunk). Ideal ranking puts every expected page first."""
    seen: set[str] = set()
    gains = []
    for d in docs[:k]:
        gains.append(1 if d in expected and d not in seen else 0)
        seen.add(d)
    dcg = sum(g / math.log2(i + 2) for i, g in enumerate(gains))
    idcg = sum(1 / math.log2(i + 2) for i in range(min(len(expected), k)))
    return dcg / idcg
