"""1.2 and 1.5 Chunking study, then retrieval mode ablation, on the fixed golden set.

python scripts/run_retrieval_ablation.py
Stage A: change ONE chunking factor at a time from the default (256 tokens, 0 overlap, header on), mode hybrid.
         Per factor the dev winner is kept; the combination of winners is then run as its own config.
Stage B: with the chosen chunking, compare retrieval modes.
Choices are made on the dev split only. held_out is reported next to it and never used to choose.
Writes eval/results/01-chunking.json and 01-retrieval.json.
"""
import json
import statistics as st
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragx.evals import retrieval_metrics as m  # noqa: E402
from ragx.ingest.parent_child import chunk_pages  # noqa: E402
from ragx.retrieve.hybrid import MODES, Retriever  # noqa: E402

RAW, OUT, CACHE = ROOT / "data" / "raw", ROOT / "eval" / "results", ROOT / "data" / "index" / "cache"
CASES = json.loads((ROOT / "eval" / "datasets" / "golden.json").read_text(encoding="utf-8"))["cases"]
PAGES = {f"{p.parent.name}/{p.name}": p.read_text(encoding="utf-8") for d in ("fastapi", "pydantic") for p in sorted((RAW / d).glob("*.md"))}
DEFAULT = dict(size=256, overlap=0.0, header=True)
K = 5
METRICS = ("hit@5", "recall@5", "precision@5", "mrr", "ndcg@10")


def score(docs: list[str], exp: set[str]) -> dict:
    return {"hit@5": m.hit_at_k(docs, exp, K), "recall@5": m.recall_at_k(docs, exp, K), "precision@5": m.precision_at_k(docs, exp, K),
            "mrr": m.reciprocal_rank(docs[:K], exp), "ndcg@10": m.ndcg_at_k(docs, exp, 10)}


def mean(rows: list[dict]) -> dict:
    return {k: round(st.mean(r[k] for r in rows), 4) for k in METRICS} | {"n": len(rows)} if rows else {}


def run(retr: Retriever, mode: str) -> dict:
    rows, lat = [], []
    for c in CASES:
        t = time.perf_counter()
        docs = [h.doc for h in retr.search(c["q"], mode, k=10)]
        lat.append((time.perf_counter() - t) * 1000)
        rows.append(score(docs, set(c["expected"])) | {"split": c["split"], "origin": c["origin"], "type": c["type"]})
    sel = lambda f: mean([r for r in rows if f(r)])
    lat.sort()
    return {"dev": sel(lambda r: r["split"] == "dev"), "held_out": sel(lambda r: r["split"] == "held_out"),
            "by_origin": {o: sel(lambda r, o=o: r["origin"] == o) for o in sorted({r["origin"] for r in rows})},
            "by_type": {t: sel(lambda r, t=t: r["type"] == t) for t in sorted({r["type"] for r in rows})},
            "p50_ms": round(lat[len(lat) // 2], 1), "p95_ms": round(lat[int(len(lat) * 0.95)], 1)}


def build(cfg: dict) -> tuple[Retriever, dict]:
    t = time.perf_counter()
    _, children = chunk_pages(PAGES, cfg["size"], cfg["overlap"])
    r = Retriever(children, header=cfg["header"], cache_dir=CACHE)
    return r, {"n_chunks": len(children), "build_s": round(time.perf_counter() - t, 1), "vector_mb": round(r.vectors.nbytes / 1e6, 2)}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    factors = {"size": [128, 256, 512], "overlap": [0.0, 0.15], "header": [True, False]}
    configs = {"default": DEFAULT}
    for f, vals in factors.items():
        for v in vals:
            if v != DEFAULT[f]:
                configs[f"{f}={v}"] = DEFAULT | {f: v}
    results = {}
    for name, cfg in configs.items():
        r, info = build(cfg)
        results[name] = {"config": cfg, **info, **run(r, "hybrid")}
        print(name, info, results[name]["dev"]["ndcg@10"], flush=True)
    best = {}  # per factor, the dev winner by nDCG@10; a tie keeps the default
    for f, vals in factors.items():
        cands = {v: results["default" if v == DEFAULT[f] else f"{f}={v}"]["dev"]["ndcg@10"] for v in vals}
        top = max(cands.values())
        best[f] = DEFAULT[f] if cands[DEFAULT[f]] == top else max(cands, key=cands.get)
    combo = {**DEFAULT, **best}
    if combo != DEFAULT:
        r, info = build(combo)
        results["combined winners"] = {"config": combo, **info, **run(r, "hybrid")}
    # the best single-factor config can beat the combination, so pick the best of everything on dev
    chosen = max(results, key=lambda n: results[n]["dev"]["ndcg@10"])
    (OUT / "01-chunking.json").write_text(json.dumps({"results": results, "chosen": chosen, "rule": "max dev nDCG@10"}, indent=2), encoding="utf-8")
    print("chosen chunking:", chosen, results[chosen]["config"])

    retr, info = build(results[chosen]["config"])
    modes = {mode: {**info, **run(retr, mode)} for mode in MODES}
    (OUT / "01-retrieval.json").write_text(json.dumps({"chunking": chosen, "modes": modes}, indent=2), encoding="utf-8")
    cols = ["hit@5", "recall@5", "precision@5", "mrr", "ndcg@10"]
    print(f"{'mode':<16}{'split':<10}" + "".join(f"{c:>12}" for c in cols) + f"{'p50 ms':>9}")
    for mode, v in modes.items():
        for split in ("dev", "held_out"):
            print(f"{mode:<16}{split:<10}" + "".join(f"{v[split][c]:>12.4f}" for c in cols) + f"{v['p50_ms']:>9}")


if __name__ == "__main__":
    main()
