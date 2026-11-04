import math

from ragx.evals.retrieval_metrics import hit_at_k, ndcg_at_k, precision_at_k, recall_at_k, reciprocal_rank

DOCS = ["a.md", "x.md", "b.md", "x.md", "x.md"]
EXP = {"a.md", "b.md", "c.md"}


def test_hit_and_recall():
    assert hit_at_k(DOCS, EXP, 1) == 1
    assert hit_at_k(DOCS, {"c.md"}, 5) == 0
    assert recall_at_k(DOCS, EXP, 1) == 1 / 3
    assert recall_at_k(DOCS, EXP, 5) == 2 / 3


def test_precision_divides_by_k():
    assert precision_at_k(DOCS, EXP, 5) == 2 / 5
    assert precision_at_k(["a.md"], {"a.md"}, 5) == 1 / 5


def test_mrr():
    assert reciprocal_rank(["x.md", "b.md"], EXP) == 0.5
    assert reciprocal_rank(["x.md"], EXP) == 0.0


def test_ndcg():
    assert ndcg_at_k(["a.md", "b.md"], {"a.md", "b.md"}) == 1.0
    assert ndcg_at_k(["x.md"], {"a.md"}) == 0.0
    assert ndcg_at_k(["a.md", "a.md", "a.md"], {"a.md"}) == 1.0  # repeat chunks of one page earn nothing extra
    expected = (1 + 1 / math.log2(4)) / (1 + 1 / math.log2(3))
    assert math.isclose(ndcg_at_k(["a.md", "x.md", "b.md"], {"a.md", "b.md"}), expected)
