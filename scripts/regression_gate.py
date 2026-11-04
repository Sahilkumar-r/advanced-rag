"""Compare a new eval result with the last good one and fail on a regression.

python scripts/regression_gate.py --new new.json --base eval/results/01-retrieval.json \
    --check modes.hybrid.dev.ndcg@10:0.03 --lower-is-better modes.hybrid.p50_ms:500
--check is "higher is better" (path:tolerance); --lower-is-better is the reverse. Prints a table; exit code 1 on any regression.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ragx.evals.gate import compare, render  # noqa: E402


def parse(spec: str, higher: bool) -> tuple[str, float, bool]:
    path, tol = spec.rsplit(":", 1)
    return path, float(tol), higher


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--new", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--check", action="append", default=[])
    ap.add_argument("--lower-is-better", action="append", default=[])
    a = ap.parse_args()
    checks = [parse(s, True) for s in a.check] + [parse(s, False) for s in a.lower_is_better]
    findings = compare(json.loads(Path(a.new).read_text(encoding="utf-8")), json.loads(Path(a.base).read_text(encoding="utf-8")), checks)
    print(render(findings))
    sys.exit(1 if any(f.regressed for f in findings) else 0)


if __name__ == "__main__":
    main()
