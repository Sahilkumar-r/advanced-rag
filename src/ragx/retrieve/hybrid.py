"""1.3 Retriever over parent child chunks: bm25, dense, hybrid (RRF), hybrid + cross encoder rerank, hybrid + MMR.

Query rewrite and HyDE need an LLM and wait for the provider adapters (phase 2.1).
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from ragx.ingest.parent_child import Child

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"
MODES = ("bm25", "dense", "hybrid", "hybrid+rerank", "hybrid+mmr")
_TOKEN = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def rrf(rankings: list[list[int]], k: int = 60) -> list[tuple[int, float]]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, cid in enumerate(ranking):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def mmr(query_sims: np.ndarray, vectors: np.ndarray, ids: list[int], k: int, lam: float = 0.7) -> list[int]:
    """Maximal marginal relevance over candidate ids: relevance to the query minus similarity to what is chosen."""
    chosen: list[int] = []
    rest = list(ids)
    while rest and len(chosen) < k:
        def score(i: int) -> float:
            redundancy = max((float(vectors[i] @ vectors[j]) for j in chosen), default=0.0)
            return lam * float(query_sims[i]) - (1 - lam) * redundancy
        best = max(rest, key=score)
        chosen.append(best)
        rest.remove(best)
    return chosen


def embed_passages(texts: list[str], embedder, cache_dir: Path | None) -> np.ndarray:
    key = hashlib.sha1((EMBED_MODEL + "\x00" + "\x00".join(texts)).encode()).hexdigest()
    f = cache_dir / f"{key}.npy" if cache_dir else None
    if f and f.exists():
        return np.load(f)
    out: list = []
    for i in range(0, len(texts), 32):
        out += list(embedder.embed(texts[i : i + 32]))
    v = np.array(out, dtype=np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    if f:
        cache_dir.mkdir(parents=True, exist_ok=True)
        np.save(f, v)
    return v


class Retriever:
    def __init__(self, children: list[Child], header: bool = True, cache_dir: Path | None = None, embedder=None):
        from fastembed import TextEmbedding

        self.children = children
        self.embedder = embedder or TextEmbedding(EMBED_MODEL)
        texts = [f"{c.heading}\n{c.text}" if header else c.text for c in children]
        self.vectors = embed_passages(texts, self.embedder, cache_dir)
        self.bm25 = BM25Okapi([tokenize(t) for t in texts])
        self._reranker = None

    def _dense(self, query: str) -> np.ndarray:
        q = np.array(next(iter(self.embedder.query_embed(query))), dtype=np.float32)
        return self.vectors @ (q / np.linalg.norm(q))

    def _rerank(self, query: str, ids: list[int]) -> list[int]:
        if self._reranker is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            self._reranker = TextCrossEncoder(RERANK_MODEL)
        scores = list(self._reranker.rerank(query, [self.children[i].text for i in ids]))
        return [i for i, _ in sorted(zip(ids, scores), key=lambda x: x[1], reverse=True)]

    def search(self, query: str, mode: str = "hybrid", k: int = 10, pool: int = 20) -> list[Child]:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        dense = self._dense(query)
        if mode == "dense":
            ids = list(map(int, np.argsort(-dense)[:k]))
        else:
            bm = self.bm25.get_scores(tokenize(query))
            if mode == "bm25":
                ids = list(map(int, np.argsort(-bm)[:k]))
            else:
                fused = [cid for cid, _ in rrf([list(map(int, np.argsort(-bm)[:pool])), list(map(int, np.argsort(-dense)[:pool]))])]
                if mode == "hybrid":
                    ids = fused[:k]
                elif mode == "hybrid+rerank":
                    ids = self._rerank(query, fused[:pool])[:k]
                else:
                    ids = mmr(dense, self.vectors, fused[:pool], k)
        return [self.children[i] for i in ids]
