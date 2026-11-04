"""The query pipeline: cache, then (plain or self) RAG through the router, with a trace and cost per query."""
from __future__ import annotations

import time
from typing import Callable

from ragx.cache.cache import Cache
from ragx.generate.answer import SYSTEM_CITE
from ragx.guardrails.checks import filter_children
from ragx.ingest.parent_child import Child, Parent
from ragx.memory.memory import contextualise
from ragx.observability.trace import Tracer
from ragx.router.router import Router
from ragx.selfrag.controller import GATE_V2, plain_rag, self_rag


class Pipeline:
    def __init__(self, retrieve: Callable[[str], list[Child]], parents: list[Parent], router: Router, cache: Cache | None = None,
                 tracer: Tracer | None = None, mode: str = "self_rag", system: str = SYSTEM_CITE, gate: str = GATE_V2,
                 url_for: Callable[[str], str | None] | None = None):
        self.retrieve, self.parents, self.router, self.cache, self.tracer = retrieve, parents, router, cache, tracer
        self.mode, self.system, self.gate, self.url_for = mode, system, gate, url_for

    def ask(self, question: str, memory: str = "", history: list | None = None) -> dict:
        t = time.perf_counter()
        if history:  # a follow up like "and how do I validate it?" needs the earlier turns to be searchable
            question = contextualise(self.router.call, question, history)
        use_cache = self.cache and not memory and not history  # answers shaped by one user's memory or conversation are never shared
        if use_cache:
            hit, kind, sim = self.cache.get(question)
            if hit is not None:
                out = {**hit, "cache": kind, "similarity": round(sim, 4), "tokens": 0, "calls": 0, "latency_ms": (time.perf_counter() - t) * 1000, "fallbacks": 0}
                out["trace_id"] = self._trace(question, out)
                return out
        before = (self.router.stats["fallbacks"], self.router.stats["calls"])
        flags: list[str] = []
        retrieve = lambda q: filter_children(self.retrieve(q), flags)  # drop chunks that carry instructions aimed at the model
        if self.mode == "self_rag":
            res = self_rag(question, retrieve, self.parents, self.router.call, system=self.system, gate=self.gate, memory=memory)
        else:
            res = plain_rag(question, retrieve, self.parents, self.router.call, system=self.system, memory=memory)
        out = {"text": res.text, "refused": res.refused, "citations": res.citations, "sources": [f"{s.doc} > {s.heading}" for s in res.sources],
               "cache": None, "similarity": 0.0, "tokens": res.tokens, "calls": len(res.calls), "latency_ms": (time.perf_counter() - t) * 1000,
               "fallbacks": self.router.stats["fallbacks"] - before[0], "steps": res.steps + flags, "_sources": res.sources,
               "source_details": [{"n": s.n, "doc": s.doc, "heading": s.heading, "text": s.text, "url": self.url_for(s.doc) if self.url_for else None} for s in res.sources]}
        if use_cache:
            self.cache.put(question, {k: out[k] for k in ("text", "refused", "citations", "sources", "_sources", "source_details")})
        out["trace_id"] = self._trace(question, out)
        return out

    def _trace(self, question: str, out: dict) -> str | None:
        if self.tracer:
            return self.tracer.record(question, cache=out["cache"], calls=out["calls"], tokens=out["tokens"], latency_ms=round(out["latency_ms"], 1),
                                      cost_usd=self.router.stats["cost_usd"], refused=out["refused"], steps=out.get("steps"))["trace_id"]
        return None
