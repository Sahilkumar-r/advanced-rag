from pathlib import Path

from ragx.evals.gate import compare, render

BASE = {"modes": {"hybrid": {"dev": {"ndcg@10": 0.88, "hit@5": 0.95}, "p50_ms": 16}}}


def test_drop_within_tolerance_passes_and_beyond_it_fails():
    ok = compare({"modes": {"hybrid": {"dev": {"ndcg@10": 0.86}}}}, BASE, [("modes.hybrid.dev.ndcg@10", 0.03, True)])
    bad = compare({"modes": {"hybrid": {"dev": {"ndcg@10": 0.84}}}}, BASE, [("modes.hybrid.dev.ndcg@10", 0.03, True)])
    assert not ok[0].regressed and bad[0].regressed and round(bad[0].delta, 2) == -0.04


def test_an_improvement_never_regresses_and_lower_is_better_flips_the_direction():
    assert not compare({"modes": {"hybrid": {"dev": {"ndcg@10": 0.95}}}}, BASE, [("modes.hybrid.dev.ndcg@10", 0.0, True)])[0].regressed
    slow = compare({"modes": {"hybrid": {"p50_ms": 600}}}, BASE, [("modes.hybrid.p50_ms", 500, False)])
    fast = compare({"modes": {"hybrid": {"p50_ms": 12}}}, BASE, [("modes.hybrid.p50_ms", 500, False)])
    assert slow[0].regressed and not fast[0].regressed


def test_a_metric_that_vanished_from_the_new_run_is_a_regression_not_a_pass():
    f = compare({"modes": {}}, BASE, [("modes.hybrid.dev.hit@5", 0.03, True)])[0]
    assert f.regressed and "missing" in f.note


def test_no_baseline_means_not_gated_and_the_table_says_so():
    f = compare({"x": 1}, {}, [("x", 0.03, True)])
    assert not f[0].regressed and "not gated" in render(f)


def test_the_committed_retrieval_baseline_has_every_metric_the_ci_gate_checks():
    import json

    base = json.loads((Path(__file__).resolve().parent.parent / "eval" / "results" / "01-retrieval.json").read_text(encoding="utf-8"))
    paths = [f"modes.hybrid.{s}.{m}" for s in ("dev", "held_out") for m in ("hit@5", "ndcg@10")]
    assert all(not f.note.startswith("no baseline") for f in compare(base, base, [(p, 0.03, True) for p in paths]))
