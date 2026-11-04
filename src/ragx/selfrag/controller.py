"""2.3 Plain RAG and the self-RAG controller (need retrieval, relevance, support and usefulness, retry cap 2).

retrieve(query) -> list[Child]; llm(tier, messages, **kw) -> Completion. Control calls use the fast tier, the answer uses the answer tier.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable

from ragx.generate.answer import LLM, REFUSAL, SYSTEM, Answer, Source, build_sources, format_context, generate
from ragx.generate.providers import Completion
from ragx.ingest.parent_child import Child, Parent

OFF_TOPIC = "I can only answer questions about the FastAPI and Pydantic documentation."


@dataclass
class Result:
    text: str
    refused: bool
    citations: list[int] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    calls: list[Completion] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    retries: int = 0

    @property
    def tokens(self) -> int:
        return sum(c.prompt_tokens + c.completion_tokens for c in self.calls)

    @property
    def latency_ms(self) -> float:
        return sum(c.latency_ms for c in self.calls if not c.cached)


def parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        return {}


def _ask(llm: LLM, system: str, user: str, res: Result, max_tokens: int = 400) -> str:
    c = llm("fast", [{"role": "system", "content": system}, {"role": "user", "content": user}], max_tokens=max_tokens)
    res.calls.append(c)
    return c.text


def _finish(res: Result, ans: Answer, sources: list[Source]) -> Result:
    res.text, res.refused, res.citations, res.sources = ans.text, ans.refused, ans.citations, sources
    return res


GATE_V1 = 'Is the question about using the FastAPI or Pydantic Python libraries? Reply JSON only: {"retrieve": true or false}.'
# v2 (experiment): v1 refused "how do I write tests for my API" because the library was not named.
GATE_V2 = ("This assistant answers questions about the FastAPI and Pydantic documentation. Reply JSON only: {\"retrieve\": true} for any question about "
           "building or testing web APIs, requests and responses, databases in an API app, data validation or serialization, or Python typing, "
           "even if the library is not named. Reply {\"retrieve\": false} only if the question is clearly unrelated to programming.")


def plain_rag(question: str, retrieve: Callable[[str], list[Child]], parents: list[Parent], llm: LLM, k: int = 4, system: str = SYSTEM, memory: str = "") -> Result:
    res = Result("", False, steps=["retrieve", "generate"])
    sources = build_sources(retrieve(question), parents, k)
    ans = generate(question, sources, llm, system=system, memory=memory)
    res.calls.append(ans.completion)
    return _finish(res, ans, sources)


def self_rag(question: str, retrieve: Callable[[str], list[Child]], parents: list[Parent], llm: LLM, k: int = 4, max_retries: int = 2,
             system: str = SYSTEM, gate: str = GATE_V1, memory: str = "") -> Result:
    res = Result("", False)
    need = parse_json(_ask(llm, gate, question, res))
    res.steps.append(f"need_retrieval={need.get('retrieve', True)}")
    if need.get("retrieve") is False:
        res.text, res.refused = OFF_TOPIC, True
        return res
    query, grounded_rule = question, ""
    while True:
        sources = build_sources(retrieve(query), parents, k)
        graded = parse_json(_ask(llm, 'Which numbered sources help answer the question? Reply JSON only: {"relevant": [source numbers]}.',
                                 f"Question: {question}\n\nSources:\n{format_context(sources)}", res))
        wanted = graded.get("relevant") if isinstance(graded.get("relevant"), list) else []
        keep = [Source(i + 1, s.doc, s.heading, s.text) for i, s in enumerate(s for s in sources if s.n in wanted)]
        res.steps.append(f"relevant={len(keep)}/{len(sources)}")
        if keep:
            ans = generate(question, keep, llm, extra_rule=grounded_rule, system=system, memory=memory)
            res.calls.append(ans.completion)
            if ans.refused:  # a refusal needs no grounding check
                return _finish(res, ans, keep)
            check = parse_json(_ask(llm, 'Check the answer against the sources. Reply JSON only: {"supported": true if every claim is stated in the sources, "useful": true if it answers the question}.',
                                    f"Question: {question}\n\nSources:\n{format_context(keep)}\n\nAnswer:\n{ans.text}", res))
            res.steps.append(f"supported={check.get('supported')} useful={check.get('useful')}")
            if check.get("supported") is not False and check.get("useful") is not False:
                return _finish(res, ans, keep)
            grounded_rule = "\n6. Use only facts stated in the sources. Drop any claim you cannot cite."
        if res.retries >= max_retries:
            res.text, res.refused, res.sources = REFUSAL, True, keep or sources
            return res
        res.retries += 1
        if not keep:  # nothing relevant: rewrite the query and search again
            query = _ask(llm, "Rewrite the question as a short documentation search query. Reply with the query only.", question, res, 100).strip() or question
            res.steps.append("rewrite")
