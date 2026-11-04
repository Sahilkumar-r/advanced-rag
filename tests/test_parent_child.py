import numpy as np

from ragx.index import ann
from ragx.ingest.parent_child import chunk_pages, ntok
from ragx.retrieve.hybrid import mmr, rrf

MD = "# T\n\n## A\n\n" + "\n\n".join(f"Paragraph {i} " + "word " * 40 for i in range(6)) + "\n\n## B\n\nShort body.\n"


def test_children_respect_size_and_point_to_parent():
    parents, children = chunk_pages({"d.md": MD}, size=100)
    assert [p.heading for p in parents] == ["T > A", "T > B"]
    assert all(ntok(c.text) <= 100 for c in children)
    assert {c.parent for c in children} == {0, 1}
    assert "".join(c.text for c in children if c.parent == 0).count("Paragraph") == 6  # nothing lost


def test_overlap_repeats_text_and_zero_does_not():
    _, none = chunk_pages({"d.md": MD}, size=100, overlap=0.0)
    _, some = chunk_pages({"d.md": MD}, size=100, overlap=0.5)
    count = lambda cs: sum(c.text.count("Paragraph") for c in cs)
    assert count(none) == 6  # 6 paragraphs in section A, the body of B has none
    assert count(some) > count(none)


def test_big_code_block_is_split():
    code = "```python\n" + "\n".join(f"x{i} = {i}" for i in range(200)) + "\n```"
    _, children = chunk_pages({"d.md": f"## C\n\n{code}\n"}, size=64)
    assert len(children) > 1 and all(ntok(c.text) <= 64 for c in children)


def test_rrf_and_mmr():
    assert rrf([[1, 2], [2, 3]])[0][0] == 2
    v = np.array([[1, 0], [0.99, 0.14], [0, 1]], dtype=np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    sims = np.array([1.0, 0.99, 0.5])
    assert mmr(sims, v, [0, 1, 2], 2, lam=0.5) == [0, 2]  # skips the near duplicate


def test_ann_flat_matches_itself_and_ivf_recall_is_bounded():
    rng = np.random.default_rng(0)
    v = rng.normal(size=(500, 16)).astype(np.float32)
    v /= np.linalg.norm(v, axis=1, keepdims=True)
    exact = ann.search(ann.build("flat", v), v[:20], 5)
    assert ann.recall_vs_exact(exact, exact) == 1.0
    ivf = ann.search(ann.build("ivf", v, nlist=8, nprobe=8), v[:20], 5)
    assert ann.recall_vs_exact(ivf, exact) == 1.0  # probing every list is exact
