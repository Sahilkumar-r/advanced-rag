"""CI retrieval regression check (no LLM, no keys): rebuild the default index and compare hybrid retrieval with the committed last good run.

python scripts/fetch_docs.py && python scripts/ci_retrieval_check.py
Same code path and golden set as scripts/run_retrieval_ablation.py. Tolerance 0.03 is a placeholder from docs/EVALS.md.
Writes the new result to the path given by --out (default eval/results/ci-retrieval.json, not committed). Exit code 1 on regression.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_retrieval_ablation as A  # noqa: E402
from ragx.evals.gate import compare, render  # noqa: E402

CHECKS = [(f"modes.hybrid.{s}.{m}", 0.03, True) for s in ("dev", "held_out") for m in ("hit@5", "ndcg@10")]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "eval" / "results" / "ci-retrieval.json"))
    a = ap.parse_args()
    retr, info = A.build(A.DEFAULT)
    new = {"chunking": A.DEFAULT, "modes": {"hybrid": {**info, **A.run(retr, "hybrid")}}}
    Path(a.out).write_text(json.dumps(new, indent=2), encoding="utf-8")
    base = json.loads((ROOT / "eval" / "results" / "01-retrieval.json").read_text(encoding="utf-8"))
    findings = compare(new, base, CHECKS)
    print(render(findings))
    sys.exit(1 if any(f.regressed for f in findings) else 0)


if __name__ == "__main__":
    main()
