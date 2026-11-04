"""2.4 Plain RAG vs self-RAG on a fixed question set, scored by the LLM judge.

python scripts/run_generation_eval.py
Set: 28 answerable golden questions (every 3rd baseline and Claude written case, a few synthetic), 8 off topic questions
from rag-demo, 6 in domain questions whose answers are not in the indexed pages. Same retriever (hybrid, default chunking) for both systems.
Latency and token numbers come from the first (uncached) run; LLM responses are cached on disk afterwards.
Writes eval/results/02-generation.json.
"""
import argparse
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragx.evals import generation as G  # noqa: E402
from ragx.generate.answer import SYSTEM, SYSTEM_CITE  # noqa: E402
from ragx.generate.providers import call_tier  # noqa: E402
from ragx.ingest.parent_child import chunk_pages  # noqa: E402
from ragx.retrieve.hybrid import Retriever  # noqa: E402
from ragx.selfrag.controller import GATE_V1, GATE_V2, plain_rag, self_rag  # noqa: E402

RAW, CACHE = ROOT / "data" / "raw", ROOT / "data" / "index" / "cache"
GOLD = json.loads((ROOT / "eval" / "datasets" / "golden.json").read_text(encoding="utf-8"))
UNANSWERABLE = [  # real FastAPI topics that live outside the indexed tutorial pages, so the right behaviour is to refuse
    "How do I protect an endpoint with OAuth2 and JWT tokens?",
    "How do I use dependencies with yield to manage a database session?",
    "How do I add a WebSocket endpoint?",
    "How do I deploy the app in a Docker container?",
    "How do I run the app with Gunicorn workers in production?",
    "How do I add GraphQL support?",
]


def question_set() -> list[dict]:
    cases = GOLD["cases"]
    pick = lambda origin, step: [c for c in cases if c["origin"] == origin][::step]
    items = [{"id": c["id"], "q": c["q"], "kind": "answerable"} for c in pick("baseline", 3) + pick("claude_written", 3) + pick("synthetic", 14)]
    items += [{"id": f"off{i}", "q": q, "kind": "off_topic"} for i, q in enumerate(GOLD["off_topic"])]
    items += [{"id": f"oos{i}", "q": q, "kind": "unanswerable"} for i, q in enumerate(UNANSWERABLE)]
    return items


def mean(xs):
    xs = [x for x in xs if x is not None]
    return round(st.mean(xs), 4) if xs else None


def summarise(rows: list[dict]) -> dict:
    ans = [r for r in rows if r["kind"] == "answerable"]
    answered = [r for r in rows if not r["refused"]]
    lat = sorted(r["latency_ms"] for r in rows)
    return {
        "n": len(rows),
        "faithfulness": mean(r["faithfulness"] for r in answered), "answer_relevancy": mean(r["relevancy"] for r in answered if r["kind"] == "answerable"),
        "citation_accuracy": mean(r["citation_accuracy"] for r in answered),
        "answers_with_a_citation": mean(float(bool(r["citations"])) for r in answered if r["kind"] == "answerable"),
        "refusal_correct": mean(float(r["refusal_ok"]) for r in rows),
        "answerable_answered": mean(float(not r["refused"]) for r in ans),
        "off_topic_refused": mean(float(r["refused"]) for r in rows if r["kind"] == "off_topic"),
        "unanswerable_refused": mean(float(r["refused"]) for r in rows if r["kind"] == "unanswerable"),
        "tokens_per_query": round(st.mean(r["tokens"] for r in rows)), "calls_per_query": round(st.mean(r["calls"] for r in rows), 2),
        "p50_latency_ms_uncached": round(lat[len(lat) // 2]), "retries_mean": round(st.mean(r["retries"] for r in rows), 2),
        "judge_unparsed": sum(1 for r in answered if r["faithfulness"] is None),
    }


def main() -> None:
    pages = {f"{p.parent.name}/{p.name}": p.read_text(encoding="utf-8") for d in ("fastapi", "pydantic") for p in sorted((RAW / d).glob("*.md"))}
    parents, children = chunk_pages(pages, 256, 0.0)
    retr = Retriever(children, cache_dir=CACHE)
    retrieve = lambda q: retr.search(q, "hybrid", k=8)
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="", help="suffix for the result file, e.g. cite2")
    ap.add_argument("--cite", action="store_true", help="use the stricter citation prompt (SYSTEM_CITE)")
    ap.add_argument("--gate2", action="store_true", help="use the broader need retrieval prompt (GATE_V2), self-RAG only")
    ap.add_argument("--systems", default="plain_rag,self_rag")
    ap.add_argument("--sample", type=int, default=0, help="run only about N questions, spread evenly over the fixed set (for the nightly run)")
    args = ap.parse_args()
    system = SYSTEM_CITE if args.cite else SYSTEM
    runners = {"plain_rag": lambda q, r, p, l: plain_rag(q, r, p, l, system=system),
               "self_rag": lambda q, r, p, l: self_rag(q, r, p, l, system=system, gate=GATE_V2 if args.gate2 else GATE_V1)}
    out = {"variant": {"cite": args.cite, "gate2": args.gate2}, "systems": {}, "rows": {}}
    items = question_set()
    if args.sample:
        items = items[:: max(1, len(items) // args.sample)]
    for name, fn in ((s, runners[s]) for s in args.systems.split(",")):
        rows = []
        for it in items:
            try:
                res = fn(it["q"], retrieve, parents, call_tier)
            except Exception as e:  # a provider outage must not hide the other questions; it is counted and reported
                rows.append({**it, "error": str(e)[:200], "refused": True, "refusal_ok": False, "citations": [], "tokens": 0, "calls": 0, "latency_ms": 0, "retries": 0,
                             "faithfulness": None, "relevancy": None, "citation_accuracy": None, "text": ""})
                print(name, it["id"], "ERROR", str(e)[:100], flush=True)
                continue
            row = {**it, "text": res.text, "refused": res.refused, "citations": res.citations, "tokens": res.tokens, "calls": len(res.calls),
                   "latency_ms": res.latency_ms, "retries": res.retries, "steps": res.steps, "refusal_ok": G.refusal_correct(it["kind"], res.refused),
                   "faithfulness": None, "relevancy": None, "citation_accuracy": None, "sources": [s.doc + " > " + s.heading for s in res.sources]}
            if not res.refused:
                d = G.judge(it["q"], res.sources, res.text, call_tier)
                row |= {"faithfulness": G.faithfulness(d), "relevancy": G.relevancy(d), "citation_accuracy": G.citation_accuracy(d), "judge": {k: v for k, v in d.items() if k != "_ok"}}
            rows.append(row)
            print(name, it["id"], it["kind"], "refused" if res.refused else "answered", row["faithfulness"], flush=True)
        out["rows"][name] = rows
        out["systems"][name] = {"overall": summarise(rows), **{k: summarise([r for r in rows if r["kind"] == k]) for k in ("answerable", "off_topic", "unanswerable")}}
        out["systems"][name]["errors"] = sum("error" in r for r in rows)
    (ROOT / "eval" / "results" / f"02-generation{'-' + args.tag if args.tag else ''}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    for n, s in out["systems"].items():
        print(n, json.dumps(s["overall"]))


if __name__ == "__main__":
    main()
