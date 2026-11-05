"""1.x Context precision (LLM judged). Needs the judge tier (Gemini, a different family than the answer model) and sends only public docs text and golden questions.

python scripts/run_context_precision_eval.py [--sample N]
For each answerable golden question it builds the exact context the answer model gets in production (hybrid search k=8, parent expansion, top 4 sources) and asks
the judge, once per question, which numbered sources contain information needed to answer it. There are no reference answers in the golden set, so "useful" means
useful for answering the question as asked; context RECALL is not measured here because it needs reference answers.
Reported: context precision (rank weighted: mean of precision@i over the useful positions, 0 when nothing is useful), the plain share of useful sources, and the share of
questions with at least one useful source. As a sanity check on the judge it also reports agreement with the independent page label (is the source on an expected page),
with the full disagreement list in the result file for a human spot check. The judge is NOT hand calibrated for this task yet.
Writes eval/results/01-context-precision.json.
"""
import argparse
import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragx.generate.answer import build_sources  # noqa: E402
from ragx.generate.providers import call_tier  # noqa: E402
from ragx.ingest.parent_child import chunk_pages  # noqa: E402
from ragx.retrieve.hybrid import Retriever  # noqa: E402
from ragx.selfrag.controller import parse_json  # noqa: E402

RAW, CACHE = ROOT / "data" / "raw", ROOT / "data" / "index" / "cache"
GOLD = json.loads((ROOT / "eval" / "datasets" / "golden.json").read_text(encoding="utf-8"))
SYSTEM = ("You grade search results for a documentation assistant. You get a question and numbered sources. "
          "A source is useful if it contains information that is needed to answer the question, fully or in part. A source on the same topic that does not help answer this question is NOT useful. "
          'Reply with JSON only: {"useful": [1 or 0 for source 1, 1 or 0 for source 2, ...]} with exactly one entry per source, in order.')


def context_precision(flags: list[int]) -> float:
    """Mean of precision@i over the useful positions (the Ragas style rank weighted score). 0 when nothing is useful."""
    hits, total = 0, 0.0
    for i, f in enumerate(flags, 1):
        if f:
            hits += 1
            total += hits / i
    return total / hits if hits else 0.0


def judge(question: str, sources) -> list[int] | None:
    body = "\n\n".join(f"[{s.n}] ({s.doc} > {s.heading})\n{s.text[:1500]}" for s in sources)
    c = call_tier("judge", [{"role": "system", "content": SYSTEM}, {"role": "user", "content": f"Question: {question}\n\nSources:\n{body}"}], max_tokens=200)
    u = parse_json(c.text).get("useful")
    return [int(bool(x)) for x in u] if isinstance(u, list) and len(u) == len(sources) else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0, help="about N questions spread evenly over the fixed set (for a quick or nightly run)")
    args = ap.parse_args()
    pages = {f"{p.parent.name}/{p.name}": p.read_text(encoding="utf-8") for d in ("fastapi", "pydantic") for p in sorted((RAW / d).glob("*.md"))}
    parents, children = chunk_pages(pages, 256, 0.0)
    retr = Retriever(children, cache_dir=CACHE)
    cases = GOLD["cases"][:: max(1, len(GOLD["cases"]) // args.sample)] if args.sample else GOLD["cases"]
    rows = []
    for c in cases:
        sources = build_sources(retr.search(c["q"], "hybrid", k=8), parents, 4)
        row = {"id": c["id"], "q": c["q"], "type": c["type"], "origin": c["origin"], "split": c["split"], "docs": [s.doc for s in sources]}
        try:
            flags = judge(c["q"], sources)
        except Exception as e:  # a provider outage is counted and reported, never dropped silently
            row["error"] = str(e)[:150]
            rows.append(row)
            print(c["id"], "ERROR", row["error"][:80], flush=True)
            continue
        if flags is None:
            row["error"] = "judge reply could not be parsed"
        else:
            row |= {"useful": flags, "on_expected_page": [int(s.doc in c["expected"]) for s in sources], "context_precision": round(context_precision(flags), 4)}
        rows.append(row)
        print(c["id"], row.get("useful"), row.get("context_precision"), flush=True)
    ok = [r for r in rows if "useful" in r]
    flat = lambda key: [x for r in ok for x in r[key]]
    j, p = flat("useful"), flat("on_expected_page")
    agree = sum(a == b for a, b in zip(j, p))
    by = lambda key: {v: round(st.mean(r["context_precision"] for r in ok if r[key] == v), 4) for v in sorted({r[key] for r in ok})}
    res = {
        "judge": "tier judge (Gemini); different family than the answer model; not hand calibrated for this task", "k_sources": 4, "retrieval": "hybrid k=8, parent expansion, as in production",
        "questions": len(rows), "judged": len(ok), "errors": len(rows) - len(ok),
        "context_precision": round(st.mean(r["context_precision"] for r in ok), 4), "useful_source_share": round(sum(j) / len(j), 4),
        "questions_with_a_useful_source": round(sum(any(r["useful"]) for r in ok) / len(ok), 4),
        "by_type": by("type"), "by_origin": by("origin"), "by_split": by("split"),
        "judge_vs_page_label": {"agreement": round(agree / len(j), 4), "judge_useful_page_wrong": sum(a and not b for a, b in zip(j, p)), "judge_not_useful_page_right": sum(b and not a for a, b in zip(j, p)), "n_sources": len(j)},
        "rows": rows,
    }
    (ROOT / "eval" / "results" / "01-context-precision.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=2))


if __name__ == "__main__":
    main()
