"""Image build step: download the embedding model and compute the chunk embeddings once, so a Space boots without doing either.

python scripts/prebuild.py     (uses FASTEMBED_CACHE_PATH if set; run by the Dockerfile after the docs are in data/raw)
Writes the embedding cache to data/index/cache, the same cache the app reads at startup.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragx.ingest.parent_child import chunk_pages  # noqa: E402
from ragx.retrieve.hybrid import Retriever  # noqa: E402


def main() -> None:
    pages = {f"{p.parent.name}/{p.name}": p.read_text(encoding="utf-8") for d in ("fastapi", "pydantic") for p in sorted((ROOT / "data" / "raw" / d).glob("*.md"))}
    if not pages:
        sys.exit("no docs in data/raw: run scripts/fetch_docs.py first")
    t = time.perf_counter()
    _, children = chunk_pages(pages, 256, 0.0)
    r = Retriever(children, cache_dir=ROOT / "data" / "index" / "cache")
    print(f"prebuilt {len(children)} chunks from {len(pages)} pages, {r.vectors.nbytes / 1e6:.1f} MB of vectors, {time.perf_counter() - t:.0f} s")


if __name__ == "__main__":
    main()
