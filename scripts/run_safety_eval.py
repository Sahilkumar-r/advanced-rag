"""4.2 Safety eval for the rule based guardrails (no LLM, no network). Runs in CI.

python scripts/run_safety_eval.py
Reports block rate on attacks, false refusal rate on benign look-alikes, PII detection and false alarms,
retrieval guard drop and keep rates, and output check accuracy. Labels were written by Claude and are unreviewed.
Writes eval/results/04-safety.json.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragx.guardrails.checks import check_input, check_output, filter_children, find_pii  # noqa: E402

DS = json.loads((ROOT / "eval" / "datasets" / "safety.json").read_text(encoding="utf-8"))
FAKE = {"{KEY}": "sk-" + "FAKE" * 6, "{GSK}": "gsk_" + "FAKE" * 6}


def x(s: str) -> str:
    for k, v in FAKE.items():
        s = s.replace(k, v)
    return s


class C:  # stands in for a retrieved chunk
    def __init__(self, text):
        self.text = text


def rate(n: int, d: int) -> float:
    return round(n / d, 4)


def main() -> None:
    inj = [(t, check_input(t).blocked) for t in DS["injection"]]
    ben = [(t, check_input(t).blocked) for t in DS["benign"]]
    pii = [(c["text"], sorted(find_pii(x(c["text"]))), sorted(c["kinds"])) for c in DS["pii"]]
    raw = [x(c["text"]) for c in DS["pii"]]
    redacted = [check_input(t).text for t in raw]
    still_leaks = [t for t, c in zip(redacted, DS["pii"]) if c["kinds"] and find_pii(t)]
    drop = [len(filter_children([C(t)])) == 0 for t in DS["retrieved_attack"]]
    keep = [len(filter_children([C(t)])) == 1 for t in DS["retrieved_benign"]]
    out = []
    for c in DS["output"]:
        v = check_output(x(c["answer"]), c["n_sources"], c["refused"], c["sources"])
        out.append((c["answer"][:50], sorted(v.flags), sorted(c["flags"]), not find_pii(v.text) or c["flags"] == []))
    res = {
        "labeller": "claude, unreviewed",
        "injection_block_rate": rate(sum(b for _, b in inj), len(inj)), "injection_n": len(inj),
        "missed_injections": [t for t, b in inj if not b],
        "benign_false_refusal_rate": rate(sum(b for _, b in ben), len(ben)), "benign_n": len(ben),
        "wrongly_blocked_benign": [t for t, b in ben if b],
        "pii_cases_exact": rate(sum(g == w for _, g, w in pii), len(pii)), "pii_n": len(pii),
        "pii_wrong": [(t, g, w) for t, g, w in pii if g != w],
        "pii_leaks_after_redaction": len(still_leaks),
        "retrieval_attack_drop_rate": rate(sum(drop), len(drop)), "retrieval_benign_keep_rate": rate(sum(keep), len(keep)),
        "output_flags_exact": rate(sum(g == w for _, g, w, _ in out), len(out)), "output_n": len(out),
        "output_wrong": [(a, g, w) for a, g, w, _ in out if g != w],
    }
    (ROOT / "eval" / "results" / "04-safety.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
