"""Hybrid retrieval: BM25 + dense embeddings fused with Reciprocal Rank Fusion, optional cross-encoder rerank."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from ragx.ingest.chunking import Chunk, chunk_markdown

EMBED_MODEL = "BAAI/bge-small-en-v1.5"
RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"
MODES = ("bm25", "dense", "hybrid", "hybrid_rerank")
_TOKEN = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def rrf(rankings: list[list[int]], k: int = 60) -> list[tuple[int, float]]:
    """Reciprocal Rank Fusion over ranked lists of ids. Returns (id, score) best first."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, cid in enumerate(ranking):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


@dataclass
class Hit:
    chunk: Chunk
    score: float
    dense: float  # cosine similarity to the query, used for the relevance guardrail

    def to_dict(self) -> dict:
        d = asdict(self.chunk)
        d.update(score=round(self.score, 4), dense=round(self.dense, 4))
        return d


def build_index(docs_dir: Path, out_dir: Path) -> int:
    from fastembed import TextEmbedding

    chunks: list[Chunk] = []
    for path in sorted(docs_dir.glob("*.md")):
        chunks += chunk_markdown(path.name, path.read_text(encoding="utf-8"), start_id=len(chunks))
    model = TextEmbedding(EMBED_MODEL)
    texts = [f"{c.heading}\n{c.text}" for c in chunks]
    out: list = []
    for i in range(0, len(texts), 32):  # small batches: one giant call was far slower on CPU
        out += list(model.embed(texts[i : i + 32]))
        print(f"embedded {min(i + 32, len(texts))}/{len(texts)}", flush=True)
    vectors = np.array(out, dtype=np.float32)
    out_dir.mkdir(parents=True, exist_ok=True)
    np.save(out_dir / "embeddings.npy", vectors)
    (out_dir / "chunks.json").write_text(json.dumps([asdict(c) for c in chunks]), encoding="utf-8")
    return len(chunks)


class Retriever:
    def __init__(self, index_dir: Path):
        from fastembed import TextEmbedding

        self.chunks = [Chunk(**c) for c in json.loads((index_dir / "chunks.json").read_text(encoding="utf-8"))]
        self.vectors = np.load(index_dir / "embeddings.npy")
        self.vectors /= np.linalg.norm(self.vectors, axis=1, keepdims=True)
        self.bm25 = BM25Okapi([tokenize(f"{c.heading} {c.text}") for c in self.chunks])
        self.embedder = TextEmbedding(EMBED_MODEL)
        self._reranker = None

    def _dense(self, query: str) -> np.ndarray:
        q = np.array(next(iter(self.embedder.query_embed(query))), dtype=np.float32)
        return self.vectors @ (q / np.linalg.norm(q))

    def _rerank(self, query: str, ids: list[int]) -> list[tuple[int, float]]:
        if self._reranker is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder

            self._reranker = TextCrossEncoder(RERANK_MODEL)
        scores = list(self._reranker.rerank(query, [self.chunks[i].text for i in ids]))
        return sorted(zip(ids, scores), key=lambda x: x[1], reverse=True)

    def search(self, query: str, mode: str = "hybrid", k: int = 5, pool: int = 20) -> list[Hit]:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        dense = self._dense(query)
        if mode == "dense":
            ranked = [(int(i), float(dense[i])) for i in np.argsort(-dense)[:k]]
        else:
            bm = self.bm25.get_scores(tokenize(query))
            if mode == "bm25":
                ranked = [(int(i), float(bm[i])) for i in np.argsort(-bm)[:k]]
            else:
                fused = rrf([list(map(int, np.argsort(-bm)[:pool])), list(map(int, np.argsort(-dense)[:pool]))])
                if mode == "hybrid":
                    ranked = fused[:k]
                else:
                    ranked = self._rerank(query, [cid for cid, _ in fused[:pool]])[:k]
        return [Hit(self.chunks[i], s, float(dense[i])) for i, s in ranked]
