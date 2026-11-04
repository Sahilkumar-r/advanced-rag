"""Phase 0 baseline: rebuild the rag-demo index and score every mode with the new metrics.

python scripts/run_baseline_eval.py
"""
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragx.evals import retrieval_metrics as m  # noqa: E402
from ragx.retrieve.baseline import MODES, Retriever, build_index  # noqa: E402

DOCS, INDEX = ROOT / "data" / "raw" / "baseline-fastapi", ROOT / "data" / "index" / "baseline"
QS = json.loads((ROOT / "eval" / "datasets" / "baseline_questions.json").read_text(encoding="utf-8"))["in_domain"]
K = 5


def main() -> None:
    if not (INDEX / "chunks.json").exists():
        print("indexed", build_index(DOCS, INDEX), "chunks")
    r = Retriever(INDEX)
    out = {"questions": len(QS), "k": K, "modes": {}}
    for mode in MODES:
        rows = []
        for q in QS:
            docs = [h.chunk.doc for h in r.search(q["q"], mode, k=10)]
            exp = set(q["expected"])
            rows.append({
                "hit@1": m.hit_at_k(docs, exp, 1), "hit@3": m.hit_at_k(docs, exp, 3), "hit@5": m.hit_at_k(docs, exp, K),
                "recall@5": m.recall_at_k(docs, exp, K), "precision@5": m.precision_at_k(docs, exp, K),
                "mrr": m.reciprocal_rank(docs[:K], exp), "ndcg@10": m.ndcg_at_k(docs, exp, 10),
            })
        out["modes"][mode] = {k: round(st.mean(row[k] for row in rows), 4) for k in rows[0]}
    path = ROOT / "eval" / "results" / "00-baseline.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    cols = list(next(iter(out["modes"].values())))
    print(f"{'mode':<15}" + "".join(f"{c:>12}" for c in cols))
    for mode, v in out["modes"].items():
        print(f"{mode:<15}" + "".join(f"{v[c]:>12.4f}" for c in cols))


if __name__ == "__main__":
    main()
