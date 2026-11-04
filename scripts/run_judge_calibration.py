"""2.4 Calibrate the judge: does it agree with the 30 labelled faithfulness cases?

python scripts/run_judge_calibration.py
The labels were written by Claude and are unreviewed (see the dataset note), so this measures agreement with Claude labels.
Writes eval/results/02-judge-calibration.json.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ragx.config import TIERS  # noqa: E402
from ragx.evals.generation import faithful_label, judge  # noqa: E402
from ragx.generate.answer import Source  # noqa: E402
from ragx.generate.providers import call_tier  # noqa: E402

DS = json.loads((ROOT / "eval" / "datasets" / "judge_calibration.json").read_text(encoding="utf-8"))


def main() -> None:
    rows = []
    for c in DS["cases"]:
        s = DS["sources"][c["source"]]
        d = judge(c["q"], [Source(1, s["doc"], "", s["text"])], c["answer"], call_tier)
        rows.append({"id": c["id"], "label": c["faithful"], "judge": faithful_label(d), "defect": c["defect"], "reply": {k: v for k, v in d.items() if k != "_ok"}})
        print(c["id"], "label", c["faithful"], "judge", rows[-1]["judge"], flush=True)
    parsed = [r for r in rows if r["judge"] is not None]
    tp = sum(r["label"] is False and r["judge"] is False for r in parsed)  # unfaithful caught
    fn = sum(r["label"] is False and r["judge"] is True for r in parsed)
    fp = sum(r["label"] is True and r["judge"] is False for r in parsed)  # faithful wrongly flagged
    tn = sum(r["label"] is True and r["judge"] is True for r in parsed)
    out = {"n": len(rows), "unparsed": len(rows) - len(parsed), "agreement": round((tp + tn) / len(parsed), 4),
           "unfaithful_recall": round(tp / (tp + fn), 4) if tp + fn else None, "unfaithful_precision": round(tp / (tp + fp), 4) if tp + fp else None,
           "confusion": {"caught_unfaithful": tp, "missed_unfaithful": fn, "false_alarm": fp, "correct_faithful": tn},
           "disagreements": [r for r in parsed if r["label"] != r["judge"]], "labeller": "claude, unreviewed", "judge_models": TIERS["judge"]}
    (ROOT / "eval" / "results" / "02-judge-calibration.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print({k: v for k, v in out.items() if k not in ("disagreements", "judge_models")})


if __name__ == "__main__":
    main()
