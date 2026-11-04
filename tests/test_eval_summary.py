import json
from pathlib import Path

from ragx.evals.summary import REGISTRY, latest_results

ROOT = Path(__file__).resolve().parent.parent


def test_missing_files_and_fields_are_skipped_and_values_carry_their_source(tmp_path):
    (tmp_path / "00-baseline.json").write_text(json.dumps({"modes": {"hybrid": {"hit@5": 1.0}}}))
    (tmp_path / "04-safety.json").write_text(json.dumps({"injection_block_rate": 0.9167}))  # other fields missing on purpose
    rows = latest_results(tmp_path)
    assert {(r["metric"], r["value"], r["file"]) for r in rows} == {("hybrid hit@5, 30 baseline questions", 1.0, "00-baseline.json"), ("injection block rate", 0.9167, "04-safety.json")}
    assert all(r["date"] for r in rows)


def test_every_registry_path_resolves_in_the_committed_results():
    """Catches a renamed result field: a metric that silently vanishes from the dashboard would otherwise go unnoticed."""
    results = ROOT / "eval" / "results"
    if not results.exists():
        return
    got = {(r["part"], r["metric"]) for r in latest_results(results)}
    missing = [(p, m, f) for p, m, f, *_ in REGISTRY if (results / f).exists() and (p, m) not in got]
    assert missing == []
