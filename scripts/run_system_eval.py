"""3.4 Pipeline eval (end to end correct answer rate) and system eval (latency, tokens, cost, fallback, cache hit rate).

python scripts/run_system_eval.py
Full path: cache, router, RAG (plain and self-RAG compared), judge. The LLM response disk cache is OFF so latency is real.
Pass 1 is cold (empty cache). Pass 2 asks synthetic paraphrases of pass 1 questions to measure the semantic cache.
A question counts as correct when: answerable -> answered, judge relevancy yes, faithfulness >= 0.8 (fixed before running);
off topic or out of corpus -> refused. Writes eval/results/03-system.json.
"""
import json
import statistics as st
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_generation_eval as GE  # noqa: E402
from ragx.cache.cache import Cache  # noqa: E402
from ragx.evals import generation as G  # noqa: E402
from ragx.generate.providers import OpenAICompat, call_tier  # noqa: E402
from ragx.ingest.parent_child import chunk_pages  # noqa: E402
from ragx.observability.trace import Tracer  # noqa: E402
from ragx.pipeline import Pipeline  # noqa: E402
from ragx.retrieve.hybrid import EMBED_MODEL, Retriever  # noqa: E402
from ragx.router.router import Router  # noqa: E402

RAW, CACHE = ROOT / "data" / "raw", ROOT / "data" / "index" / "cache"
GOLD_TYPE = {c["id"]: c["type"] for c in GE.GOLD["cases"]}


def pct(xs, p):
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(len(xs) * p))])


def main() -> None:
    from fastembed import TextEmbedding

    pages = {f"{p.parent.name}/{p.name}": p.read_text(encoding="utf-8") for d in ("fastapi", "pydantic") for p in sorted((RAW / d).glob("*.md"))}
    parents, children = chunk_pages(pages, 256, 0.0)
    retr = Retriever(children, cache_dir=CACHE)
    emb = TextEmbedding(EMBED_MODEL)
    embed = lambda q: (lambda v: v / np.linalg.norm(v))(np.array(next(iter(emb.query_embed(q))), dtype=np.float32))
    threshold = json.loads((ROOT / "eval" / "results" / "03-cache.json").read_text(encoding="utf-8"))["chosen"]["threshold"]
    para = json.loads((ROOT / "eval" / "datasets" / "paraphrases.json").read_text(encoding="utf-8"))
    items = GE.question_set()
    out = {"cache_threshold": threshold, "systems": {}}
    for mode in ("plain_rag", "self_rag"):
        router = Router(client=lambda p, m: OpenAICompat(p, m, cache=False))
        pipe = Pipeline(lambda q: retr.search(q, "hybrid", k=8), parents, router, Cache(embed, threshold=threshold, namespace="eval"),
                        Tracer(ROOT / "traces" / f"system-eval-{mode}.jsonl"), mode=mode)
        rows = []
        for it in items:
            try:
                o = pipe.ask(it["q"])
            except Exception as e:  # an outage is counted and reported, not hidden
                rows.append({**it, "error": str(e)[:150], "correct": False, "latency_ms": 0, "tokens": 0, "refused": True, "text": ""})
                print(mode, it["id"], "ERROR", str(e)[:80], flush=True)
                continue
            row = {**it, "refused": o["refused"], "text": o["text"], "latency_ms": o["latency_ms"], "tokens": o["tokens"], "calls": o["calls"], "fallbacks": o["fallbacks"],
                   "gold_type": GOLD_TYPE.get(it["id"], it["kind"]), "cache": o["cache"], "similarity": o["similarity"]}
            if it["kind"] != "answerable":
                row["correct"] = o["refused"]
            elif o["refused"]:
                row["correct"] = False
            else:
                try:
                    d = G.judge(it["q"], o["_sources"], o["text"], call_tier)
                except Exception as e:  # judge outage: counted as not correct and reported as judge_error, never silently dropped
                    d = {}
                    row["judge_error"] = str(e)[:120]
                f, r = G.faithfulness(d), G.relevancy(d)
                row |= {"faithfulness": f, "relevancy": r, "correct": bool(f is not None and f >= 0.8 and r == 1.0)}
            rows.append(row)
            print(mode, it["id"], row["correct"], flush=True)
        by = lambda f: [r for r in rows if f(r)]
        rate = lambda rs: round(sum(r["correct"] for r in rs) / len(rs), 4) if rs else None
        lat = [r["latency_ms"] for r in rows if not r.get("error")]
        # pass 2: paraphrases of answerable questions
        first = {r["id"]: r for r in rows}
        hits = []
        for cid, text in para.items():
            if cid not in first or first[cid].get("error") or first[cid]["refused"]:
                continue
            o = pipe.ask(text)
            hits.append({"id": cid, "cache": o["cache"], "same_answer": o["cache"] is not None and o["text"] == first[cid]["text"], "latency_ms": o["latency_ms"]})
        hit = [h for h in hits if h["cache"]]
        s = router.stats
        out["systems"][mode] = {
            "pipeline": {"correct_overall": rate(rows), "n": len(rows), "by_kind": {k: rate(by(lambda r, k=k: r["kind"] == k)) for k in ("answerable", "off_topic", "unanswerable")},
                         "by_question_type": {t: [rate(by(lambda r, t=t: r.get("gold_type") == t)), len(by(lambda r, t=t: r.get("gold_type") == t))] for t in sorted({r.get("gold_type") for r in rows if r.get("gold_type")})},
                         "errors": sum("error" in r for r in rows), "judge_errors": sum("judge_error" in r for r in rows)},
            "system": {"p50_ms": pct(lat, 0.5), "p95_ms": pct(lat, 0.95), "tokens_per_query": round(st.mean(r["tokens"] for r in rows)), "calls_per_query": round(st.mean(r.get("calls", 0) for r in rows), 2),
                       "cost_usd": s["cost_usd"], "calls_by_provider": dict(s["by_provider"]), "provider_errors": s["errors"],
                       "fallback_rate": round(s["fallbacks"] / s["calls"], 4) if s["calls"] else None, "openai_enabled": router._openai_ready(),
                       "paraphrase_n": len(hits), "paraphrase_hit_rate": round(len(hit) / len(hits), 4) if hits else None,
                       "paraphrase_wrong_hits": sum(not h["same_answer"] for h in hit), "warm_hit_p50_ms": pct([h["latency_ms"] for h in hit], 0.5) if hit else None},
            "rows": rows, "paraphrase_rows": hits}
        print(mode, json.dumps({k: v for k, v in out["systems"][mode].items() if k in ("pipeline", "system")}), flush=True)
    (ROOT / "eval" / "results" / "03-system.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
