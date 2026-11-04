import json

import numpy as np

from ragx.cache.cache import Cache, normalise
from ragx.generate.providers import Completion
from ragx.ingest.parent_child import Child, Parent
from ragx.observability.trace import Tracer
from ragx.pipeline import Pipeline
from ragx.router.router import Router

VECS = {"how do i declare a path parameter": [1, 0], "how to declare path params": [0.98, 0.2], "how do i read a cookie": [0, 1]}


def embed(q):
    v = np.array(VECS[normalise(q)], dtype=np.float32)
    return v / np.linalg.norm(v)


def test_exact_semantic_and_threshold():
    c = Cache(embed, threshold=0.9)
    c.put("How do I declare a path parameter?", {"text": "A"})
    assert c.get("how do i DECLARE a path parameter")[1] == "exact"
    assert c.get("How to declare path params")[1] == "semantic"
    assert c.get("How do I read a cookie")[0] is None  # similarity 0, not a hit
    assert c.stats == {"exact": 1, "semantic": 1, "miss": 1}


def test_ttl_and_namespace():
    t = [0.0]
    c = Cache(None, ttl_s=10, namespace="v1", now=lambda: t[0])
    c.put("q", {"text": "A"})
    assert c.get("q")[1] == "exact"
    t[0] = 11
    assert c.get("q")[0] is None
    c2 = Cache(None, namespace="v2")
    c2.exact = c.exact
    assert c2.get("q")[0] is None  # an entry from another namespace is never served


class FakeClient:
    def complete(self, messages, **kw):
        return Completion("Use Path() [1]", "fake", "m", 10, 5, 3.0)


def test_pipeline_second_ask_is_a_cache_hit_with_zero_calls(tmp_path):
    parents = [Parent(0, "a.md", "A", "Use Path()")]
    children = [Child(0, "a.md", "A", "Use Path()", 0)]
    router = Router(tiers={"answer": [("f", "m")], "fast": [("f", "m")]}, client=lambda p, m: FakeClient(), quotas={}, spend_file=tmp_path / "s.json")
    tracer = Tracer(tmp_path / "t.jsonl")
    p = Pipeline(lambda q: children, parents, router, Cache(None), tracer, mode="plain_rag")
    first, second = p.ask("How do I declare a path parameter?"), p.ask("how do i declare a path parameter")
    assert first["cache"] is None and first["calls"] == 1 and second["cache"] == "exact" and second["calls"] == 0
    rows = [json.loads(l) for l in (tmp_path / "t.jsonl").read_text().splitlines()]
    assert len(rows) == 2 and "How do I" not in json.dumps(rows)  # question stored as a hash only
