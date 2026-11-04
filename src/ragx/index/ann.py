"""1.3 Vector indexes behind one interface: FAISS flat (exact), HNSW and IVF. Inner product on unit vectors = cosine.

Qdrant was dropped: its embedded mode scans every vector, so it cannot show HNSW behaviour without a server.
"""
from __future__ import annotations

import faiss
import numpy as np


def build(kind: str, vectors: np.ndarray, **p) -> faiss.Index:
    """kind: flat | hnsw (M, ef_construction, ef_search) | ivf (nlist, nprobe)."""
    v = np.ascontiguousarray(vectors, dtype=np.float32)
    d = v.shape[1]
    if kind == "flat":
        idx = faiss.IndexFlatIP(d)
    elif kind == "hnsw":
        idx = faiss.IndexHNSWFlat(d, p.get("M", 32), faiss.METRIC_INNER_PRODUCT)
        idx.hnsw.efConstruction = p.get("ef_construction", 200)
        idx.hnsw.efSearch = p.get("ef_search", 64)
    elif kind == "ivf":
        idx = faiss.IndexIVFFlat(faiss.IndexFlatIP(d), d, p["nlist"], faiss.METRIC_INNER_PRODUCT)
        idx.train(v)
        idx.nprobe = p.get("nprobe", 8)
    else:
        raise ValueError(kind)
    idx.add(v)
    return idx


def search(idx: faiss.Index, queries: np.ndarray, k: int) -> np.ndarray:
    """Returns ids, shape (n_queries, k); -1 pads when fewer than k were found."""
    return idx.search(np.ascontiguousarray(queries, dtype=np.float32), k)[1]


def recall_vs_exact(found: np.ndarray, exact: np.ndarray) -> float:
    """Mean overlap of the ANN top k with the exact top k."""
    return float(np.mean([len(set(f) & set(e)) / len(e) for f, e in zip(found, exact)]))


def size_bytes(idx: faiss.Index) -> int:
    return len(faiss.serialize_index(idx))
