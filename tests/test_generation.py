from ragx.generate.answer import REFUSAL, build_sources, parse_citations
from ragx.generate.providers import Completion
from ragx.ingest.parent_child import Child, Parent
from ragx.selfrag.controller import OFF_TOPIC, plain_rag, self_rag

PARENTS = [Parent(0, "a.md", "A", "Use Path() for path params."), Parent(1, "b.md", "B", "x " * 2000)]
CHILDREN = [Child(0, "a.md", "A", "Use Path()", 0), Child(1, "a.md", "A", "dup of parent 0", 0), Child(2, "b.md", "B", "small child", 1)]


def fake_llm(routes):
    """routes: substring of the system prompt -> reply. First match wins."""
    calls = []

    def llm(tier, messages, **kw):
        calls.append(tier)
        sys = messages[0]["content"]
        for key, reply in routes:
            if key in sys:
                return Completion(reply() if callable(reply) else reply, "mock", "mock", 10, 5, 1.0)
        raise AssertionError("unrouted prompt: " + sys[:60])

    llm.calls = calls
    return llm


def test_sources_dedupe_parents_and_fall_back_to_child_when_parent_too_long():
    s = build_sources(CHILDREN, PARENTS, k=4, max_parent_tokens=100)
    assert [x.doc for x in s] == ["a.md", "b.md"]
    assert s[0].text.startswith("Use Path()") and s[1].text == "small child"


def test_citations_ignore_out_of_range():
    assert parse_citations("yes [1][3] and [9]", 3) == [1, 3]


def test_fullwidth_bracket_citations_are_normalised_so_they_count():
    llm = fake_llm([("ONLY the numbered sources", "Use Path() 【1】 and also 【2】.")])
    r = plain_rag("how?", lambda q: CHILDREN, PARENTS, llm)
    assert r.text == "Use Path() [1] and also [2]." and r.citations == [1, 2]


def test_plain_rag_answers_with_citation():
    llm = fake_llm([("ONLY the numbered sources", "Use Path() [1]")])
    r = plain_rag("how?", lambda q: CHILDREN, PARENTS, llm)
    assert r.citations == [1] and not r.refused and r.tokens == 15


def test_self_rag_happy_path_makes_four_calls():
    llm = fake_llm([("FastAPI or Pydantic", '{"retrieve": true}'), ("Which numbered", '{"relevant": [1]}'),
                    ("ONLY the numbered sources", "Use Path() [1]"), ("Check the answer", '{"supported": true, "useful": true}')])
    r = self_rag("how?", lambda q: CHILDREN, PARENTS, llm)
    assert not r.refused and r.citations == [1] and r.retries == 0 and len(llm.calls) == 4


def test_self_rag_off_topic_stops_before_retrieval():
    retrieved = []
    llm = fake_llm([("FastAPI or Pydantic", '{"retrieve": false}')])
    r = self_rag("capital of France?", lambda q: retrieved.append(q) or CHILDREN, PARENTS, llm)
    assert r.refused and r.text == OFF_TOPIC and not retrieved


def test_self_rag_irrelevant_sources_retry_then_refuse_at_cap():
    llm = fake_llm([("FastAPI or Pydantic", '{"retrieve": true}'), ("Which numbered", '{"relevant": []}'), ("Rewrite", "path params")])
    r = self_rag("how?", lambda q: CHILDREN, PARENTS, llm, max_retries=2)
    assert r.refused and r.text == REFUSAL and r.retries == 2 and r.steps.count("rewrite") == 2


def test_self_rag_unsupported_answer_retries_with_stricter_rule_then_succeeds():
    checks = iter(['{"supported": false, "useful": true}', '{"supported": true, "useful": true}'])
    llm = fake_llm([("FastAPI or Pydantic", '{"retrieve": true}'), ("Which numbered", '{"relevant": [1]}'),
                    ("ONLY the numbered sources", "Use Path() [1]"), ("Check the answer", lambda: next(checks))])
    r = self_rag("how?", lambda q: CHILDREN, PARENTS, llm)
    assert not r.refused and r.retries == 1
