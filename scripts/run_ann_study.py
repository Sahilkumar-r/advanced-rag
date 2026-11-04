"""1.5 ANN study: FAISS flat vs HNSW vs IVF on a SYNTHETIC 100k vector corpus.

python scripts/run_ann_study.py
The synthetic vectors are real chunk embeddings plus gaussian noise, renormalised. They are clustered like the real
ones but are not real text, so recall and latency here describe the index types, not retrieval quality on the docs.
Queries are made the same way with another seed and are not in the index. Writes eval/results/01-ann.json.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragx.index import ann  # noqa: E402
from ragx.ingest.parent_child import chunk_pages  # noqa: E402
from ragx.retrieve.hybrid import Retriever  # noqa: E402

RAW, CACHE = ROOT / "data" / "raw", ROOT / "data" / "index" / "cache"
N, NQ, K, NOISE = 100_000, 300, 10, 0.02


def synth(base: np.ndarray, n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = base[rng.integers(0, len(base), n)] + rng.normal(0, NOISE, (n, base.shape[1])).astype(np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def timed(fn):
    t = time.perf_counter()
    out = fn()
    return out, time.perf_counter() - t


def latency_ms(idx, q: np.ndarray) -> float:
    ts = []
    for row in q:
        t = time.perf_counter()
        ann.search(idx, row[None], K)
        ts.append((time.perf_counter() - t) * 1000)
    return round(float(np.median(ts)), 3)


def main() -> None:
    pages = {f"{p.parent.name}/{p.name}": p.read_text(encoding="utf-8") for d in ("fastapi", "pydantic") for p in sorted((RAW / d).glob("*.md"))}
    _, children = chunk_pages(pages, 256, 0.0)
    base = Retriever(children, cache_dir=CACHE).vectors
    corpus, queries = synth(base, N, 1), synth(base, NQ, 2)
    flat, t_flat = timed(lambda: ann.build("flat", corpus))
    exact = ann.search(flat, queries, K)
    rows = [{"index": "flat", "params": {}, "recall@10": 1.0, "p50_ms": latency_ms(flat, queries), "build_s": round(t_flat, 2), "size_mb": round(ann.size_bytes(flat) / 1e6, 1)}]
    for M in (16, 32):
        idx, t = timed(lambda: ann.build("hnsw", corpus, M=M, ef_construction=200))
        for ef in (16, 64, 256):
            idx.hnsw.efSearch = ef
            rows.append({"index": "hnsw", "params": {"M": M, "ef_search": ef}, "recall@10": round(ann.recall_vs_exact(ann.search(idx, queries, K), exact), 4),
                         "p50_ms": latency_ms(idx, queries), "build_s": round(t, 2), "size_mb": round(ann.size_bytes(idx) / 1e6, 1)})
        print("hnsw", M, "done", flush=True)
    for nlist in (256, 1024):
        idx, t = timed(lambda: ann.build("ivf", corpus, nlist=nlist))
        for nprobe in (1, 8, 32):
            idx.nprobe = nprobe
            rows.append({"index": "ivf", "params": {"nlist": nlist, "nprobe": nprobe}, "recall@10": round(ann.recall_vs_exact(ann.search(idx, queries, K), exact), 4),
                         "p50_ms": latency_ms(idx, queries), "build_s": round(t, 2), "size_mb": round(ann.size_bytes(idx) / 1e6, 1)})
        print("ivf", nlist, "done", flush=True)
    out = {"synthetic": True, "n_vectors": N, "n_queries": NQ, "dim": int(base.shape[1]), "noise_std": NOISE, "rows": rows}
    (ROOT / "eval" / "results" / "01-ann.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    for r in rows:
        print(f"{r['index']:<6}{str(r['params']):<34}recall@10={r['recall@10']:<8}p50={r['p50_ms']:<8}ms build={r['build_s']}s size={r['size_mb']}MB")


if __name__ == "__main__":
    main()
