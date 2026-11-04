"""3.2 Tune the semantic cache threshold and measure wrong hits.

python scripts/tune_cache.py
Cache = all golden questions. Two probes:
  paraphrases (synthetic, written by the fast model for 40 answerable cases): should hit, and hit the right entry.
  other questions: every golden question searched against all OTHER questions: any hit above the threshold whose expected pages do not overlap
  the query's is a WRONG hit (the cache would return an answer for a different question).
Proxy limit: two questions with overlapping pages can still need different answers, so wrong hits are a floor, not a ceiling.
Rule: the lowest threshold whose wrong hit rate on other questions is at most 1 percent, so as many paraphrases as possible hit.
Writes eval/datasets/paraphrases.json and eval/results/03-cache.json.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragx.generate.providers import call_tier  # noqa: E402
from ragx.retrieve.hybrid import EMBED_MODEL  # noqa: E402

GOLD = json.loads((ROOT / "eval" / "datasets" / "golden.json").read_text(encoding="utf-8"))["cases"]
PARA = ROOT / "eval" / "datasets" / "paraphrases.json"


def paraphrases() -> dict[str, str]:
    if PARA.exists():
        return json.loads(PARA.read_text(encoding="utf-8"))
    out = {}
    for c in [c for c in GOLD if c["origin"] != "synthetic"][::2][:40]:
        t = call_tier("fast", [{"role": "system", "content": "Rewrite the question with different wording and the same meaning. Reply with the question only."},
                               {"role": "user", "content": c["q"]}], max_tokens=120).text.strip()
        out[c["id"]] = t
    PARA.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return out


def main() -> None:
    from fastembed import TextEmbedding

    emb = TextEmbedding(EMBED_MODEL)
    embed = lambda texts: np.array([v / np.linalg.norm(v) for v in emb.query_embed(texts)], dtype=np.float32)
    para = paraphrases()
    qs = [c["q"] for c in GOLD]
    E = embed(qs)
    exp = [set(c["expected"]) for c in GOLD]
    idx = {c["id"]: i for i, c in enumerate(GOLD)}
    P = embed(list(para.values()))
    pids = [idx[k] for k in para]
    S = E @ E.T
    np.fill_diagonal(S, -1)  # a question is not its own neighbour in the wrong hit probe
    other_best = S.argmax(1)
    other_sim = S.max(1)
    sims = P @ E.T
    p_best, p_sim = sims.argmax(1), sims.max(1)
    rows = []
    for t in [x / 100 for x in range(70, 100, 2)] + [0.99]:
        hit = other_sim >= t
        wrong = hit & np.array([not (exp[i] & exp[other_best[i]]) for i in range(len(GOLD))])
        p_hit = p_sim >= t
        p_right = p_hit & np.array([p_best[j] == pids[j] or bool(exp[pids[j]] & exp[p_best[j]]) for j in range(len(pids))])
        rows.append({"threshold": t, "paraphrase_hit_rate": round(float(p_hit.mean()), 4), "paraphrase_right_hit_rate": round(float(p_right.mean()), 4),
                     "other_question_hit_rate": round(float(hit.mean()), 4), "wrong_hit_rate": round(float(wrong.mean()), 4)})
    ok = [r for r in rows if r["wrong_hit_rate"] <= 0.01]
    chosen = min(ok, key=lambda r: r["threshold"]) if ok else rows[-1]
    out = {"n_cache_entries": len(qs), "n_paraphrases": len(para), "paraphrases": "synthetic, written by the fast tier model", "chosen": chosen, "rows": rows,
           "rule": "lowest threshold with wrong hit rate <= 1%"}
    (ROOT / "eval" / "results" / "03-cache.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("t     para_hit  para_right  other_hit  WRONG")
    for r in rows:
        print(f"{r['threshold']:.2f}  {r['paraphrase_hit_rate']:<9} {r['paraphrase_right_hit_rate']:<11} {r['other_question_hit_rate']:<10} {r['wrong_hit_rate']}")
    print("chosen", chosen)


if __name__ == "__main__":
    main()
