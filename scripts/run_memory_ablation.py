"""4.3 Memory ablation on multi turn cases: retrieval for the follow up with and without short term memory.

python scripts/run_memory_ablation.py
OFF: search with the follow up question alone. ON: rewrite it as a standalone question using the earlier turns, then search.
Measures retrieval only (page level, hybrid, default chunking). Long term memory is not measured here: it changes answers, not search.
Writes eval/results/04-memory.json.
"""
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragx.evals import retrieval_metrics as m  # noqa: E402
from ragx.generate.providers import call_tier  # noqa: E402
from ragx.ingest.parent_child import chunk_pages  # noqa: E402
from ragx.memory.memory import contextualise  # noqa: E402
from ragx.retrieve.hybrid import Retriever  # noqa: E402

RAW, CACHE = ROOT / "data" / "raw", ROOT / "data" / "index" / "cache"
CASES = json.loads((ROOT / "eval" / "datasets" / "multiturn.json").read_text(encoding="utf-8"))["cases"]


def main() -> None:
    pages = {f"{p.parent.name}/{p.name}": p.read_text(encoding="utf-8") for d in ("fastapi", "pydantic") for p in sorted((RAW / d).glob("*.md"))}
    _, children = chunk_pages(pages, 256, 0.0)
    retr = Retriever(children, cache_dir=CACHE)
    rows = {"memory_off": [], "memory_on": []}
    detail = []
    for c in CASES:
        standalone = contextualise(call_tier, c["q"], [tuple(t) for t in c["history"]])
        exp = set(c["expected"])
        for name, q in (("memory_off", c["q"]), ("memory_on", standalone)):
            docs = [h.doc for h in retr.search(q, "hybrid", k=10)]
            rows[name].append({"hit@5": m.hit_at_k(docs, exp, 5), "recall@5": m.recall_at_k(docs, exp, 5), "mrr": m.reciprocal_rank(docs[:5], exp), "ndcg@10": m.ndcg_at_k(docs, exp, 10)})
        detail.append({"id": c["id"], "q": c["q"], "standalone": standalone, "hit_off": rows["memory_off"][-1]["hit@5"], "hit_on": rows["memory_on"][-1]["hit@5"]})
    out = {"n": len(CASES), "labeller": "claude, unreviewed", "retrieval_only": True,
           **{k: {x: round(st.mean(r[x] for r in v), 4) for x in v[0]} for k, v in rows.items()}, "cases": detail}
    (ROOT / "eval" / "results" / "04-memory.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("n", "memory_off", "memory_on")}, indent=2))


if __name__ == "__main__":
    main()
