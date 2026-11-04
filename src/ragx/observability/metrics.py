"""Online metrics: Prometheus counters and histograms (scraped from /metrics) plus a rolling window for the admin dashboard.

Covers the online signals in docs/EVALS.md section 7 that need no ground truth: refusal and guardrail rates, cache hit rate, fallback rate,
latency, tokens, cost, thumbs feedback, and a sampled reference free faithfulness score from the judge. No question text is ever a label.
"""
from __future__ import annotations

import statistics as st
from collections import Counter, deque

from prometheus_client import CollectorRegistry, Counter as PCounter, Histogram, generate_latest

LAT_BUCKETS = (0.05, 0.25, 1, 2.5, 5, 10, 20, 45, 90)


def _p(xs: list[float], q: float) -> float | None:
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(len(xs) * q))], 1) if xs else None


class Observer:
    def __init__(self, window: int = 500):
        self.reg = CollectorRegistry()
        r = self.reg
        self.http = PCounter("ragx_http_requests_total", "HTTP requests", ["route", "method", "status"], registry=r)
        self.http_s = Histogram("ragx_http_request_seconds", "HTTP latency", ["route"], buckets=LAT_BUCKETS, registry=r)
        self.asks = PCounter("ragx_ask_total", "Questions by outcome", ["outcome", "cache", "modality"], registry=r)
        self.ask_s = Histogram("ragx_ask_seconds", "End to end answer latency", ["modality"], buckets=LAT_BUCKETS, registry=r)
        self.tokens = PCounter("ragx_tokens_total", "LLM tokens", ["kind"], registry=r)
        self.guard = PCounter("ragx_guardrail_total", "Guardrail triggers", ["kind"], registry=r)
        self.llm = PCounter("ragx_llm_calls_total", "LLM provider calls", ["provider", "tier", "status"], registry=r)
        self.llm_s = Histogram("ragx_llm_seconds", "LLM call latency", ["provider"], buckets=LAT_BUCKETS, registry=r)
        self.fallbacks = PCounter("ragx_llm_fallbacks_total", "Calls served by a fallback provider", registry=r)
        self.cost = PCounter("ragx_cost_usd_total", "Paid provider spend in USD", registry=r)
        self.feedback = PCounter("ragx_feedback_total", "Thumbs feedback", ["value"], registry=r)
        self.faith = Histogram("ragx_online_faithfulness", "Judge faithfulness on a sampled slice of live answers", buckets=(0.25, 0.5, 0.75, 0.9, 1.0), registry=r)
        self.judged = PCounter("ragx_online_judged_total", "Sampled answers scored by the judge", ["result"], registry=r)
        self.lat: deque = deque(maxlen=window)  # ms, uncached asks only
        self.tok: deque = deque(maxlen=window)
        self.n = Counter()
        self.faiths: deque = deque(maxlen=window)

    # --- recording ---------------------------------------------------------
    def request(self, route: str, method: str, status: int, seconds: float) -> None:
        self.http.labels(route, method, str(status)).inc()
        self.http_s.labels(route).observe(seconds)

    def ask(self, outcome: str, cache: str | None, latency_ms: float, tokens: int = 0, modality: str = "text") -> None:
        """outcome: answered | refused | blocked."""
        self.asks.labels(outcome, cache or "none", modality).inc()
        self.ask_s.labels(modality).observe(latency_ms / 1000)
        self.n[outcome] += 1
        if cache:
            self.n["cache_hit"] += 1
        else:
            self.lat.append(latency_ms)
            self.tok.append(tokens)

    def tokens_used(self, prompt: int, completion: int) -> None:
        self.tokens.labels("prompt").inc(prompt)
        self.tokens.labels("completion").inc(completion)

    def guardrail(self, kind: str) -> None:
        self.guard.labels(kind).inc()
        self.n["guardrail:" + kind] += 1

    def llm_call(self, provider: str, tier: str, ok: bool, seconds: float, prompt: int = 0, completion: int = 0, fallback: bool = False, cost: float = 0.0) -> None:
        self.llm.labels(provider, tier, "ok" if ok else "error").inc()
        self.n[f"llm:{provider}:{'ok' if ok else 'error'}"] += 1
        if ok:
            self.llm_s.labels(provider).observe(seconds)
            self.tokens_used(prompt, completion)
            if fallback:
                self.fallbacks.inc()
                self.n["fallbacks"] += 1
            if cost:
                self.cost.inc(cost)

    def thumbs(self, value: int) -> None:
        self.feedback.labels("up" if value > 0 else "down").inc()
        self.n["thumbs_up" if value > 0 else "thumbs_down"] += 1

    def online_faithfulness(self, score: float | None) -> None:
        if score is None:
            self.judged.labels("unparsed").inc()
            return
        self.faith.observe(score)
        self.judged.labels("scored").inc()
        self.faiths.append(score)

    # --- reading -----------------------------------------------------------
    def exposition(self) -> bytes:
        return generate_latest(self.reg)

    def snapshot(self) -> dict:
        n, asks = self.n, sum(self.n[k] for k in ("answered", "refused", "blocked"))
        calls = sum(v for k, v in n.items() if k.startswith("llm:") and k.endswith(":ok"))
        errs = sum(v for k, v in n.items() if k.startswith("llm:") and k.endswith(":error"))
        up, down = n["thumbs_up"], n["thumbs_down"]
        return {
            "asks": asks, "refusal_rate": round(n["refused"] / asks, 4) if asks else None, "blocked_rate": round(n["blocked"] / asks, 4) if asks else None,
            "cache_hit_rate": round(n["cache_hit"] / asks, 4) if asks else None,
            "latency_ms_p50_uncached": _p(list(self.lat), 0.5), "latency_ms_p95_uncached": _p(list(self.lat), 0.95), "latency_window": len(self.lat),
            "tokens_per_uncached_ask": round(st.mean(self.tok)) if self.tok else None,
            "llm_calls_ok": calls, "llm_errors": errs, "fallback_rate": round(n["fallbacks"] / calls, 4) if calls else None,
            "providers": {k.split(":")[1] + ":" + k.split(":")[2]: v for k, v in n.items() if k.startswith("llm:")},
            "guardrails": {k.split(":", 1)[1]: v for k, v in n.items() if k.startswith("guardrail:")},
            "thumbs_up": up, "thumbs_down": down, "thumbs_up_rate": round(up / (up + down), 4) if up + down else None,
            "online_faithfulness_mean": round(st.mean(self.faiths), 4) if self.faiths else None, "online_faithfulness_n": len(self.faiths),
        }
