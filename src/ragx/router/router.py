"""3.1 Router: ordered fallback per tier, circuit breaker, quota counters, capped OpenAI last resort.

Same call shape as providers.call_tier, so callers swap one for the other.
OpenAI is OFF unless OPENAI_MODEL and both price variables are set (we do not guess prices) and budget remains.
It is never used for the judge tier: the judge must be a different model family than the gpt-oss answer model.
"""
from __future__ import annotations

import json
import os
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Callable

from ragx.config import ROOT, TIERS, load_env
from ragx.generate.providers import Completion, OpenAICompat, ProviderError

# Limits as written in docs/FREE-APIS.md (third party pages, 2026-11-04, unverified). None = no hard cap known.
QUOTAS = {"groq": {"rpm": 30, "rpd": 1000}, "openrouter": {"rpm": 20, "rpd": 50}}
SPEND_FILE = ROOT / "data" / "state" / "openai_spend.json"


class Router:
    def __init__(self, tiers: dict | None = None, client: Callable[[str, str], object] | None = None, breaker_threshold: int = 3,
                 cooldown_s: float = 60.0, quotas: dict | None = None, now: Callable[[], float] = time.time, spend_file: Path = SPEND_FILE,
                 on_call: Callable[..., None] | None = None):
        load_env()
        self.on_call = on_call  # observer hook: called once per provider attempt with provider, tier, ok, seconds, tokens, fallback, cost
        self.tiers = tiers or TIERS
        self.client = client or (lambda p, m: OpenAICompat(p, m, cache=False))  # prompts can hold user memory: never write them to the disk cache
        self.threshold, self.cooldown, self.now = breaker_threshold, cooldown_s, now
        self.quotas = QUOTAS if quotas is None else quotas
        self.spend_file = spend_file
        self.fail: dict[str, int] = defaultdict(int)
        self.open_until: dict[str, float] = {}
        self.window: dict[str, deque] = defaultdict(deque)  # provider -> request timestamps in the last day
        self.stats = {"calls": 0, "fallbacks": 0, "errors": 0, "skipped_open": 0, "skipped_quota": 0, "by_provider": defaultdict(int), "cost_usd": 0.0}

    # --- OpenAI budget -------------------------------------------------
    def _openai_ready(self) -> bool:
        need = ("OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_PRICE_IN_PER_MTOK", "OPENAI_PRICE_OUT_PER_MTOK", "OPENAI_BUDGET_USD")
        return all(os.environ.get(k) for k in need) and self.spent() < float(os.environ["OPENAI_BUDGET_USD"])

    def spent(self) -> float:
        try:
            return float(json.loads(self.spend_file.read_text())["usd"])
        except (OSError, ValueError, KeyError):
            return 0.0

    def _charge(self, c: Completion) -> float:
        cost = (c.prompt_tokens * float(os.environ["OPENAI_PRICE_IN_PER_MTOK"]) + c.completion_tokens * float(os.environ["OPENAI_PRICE_OUT_PER_MTOK"])) / 1e6
        self.spend_file.parent.mkdir(parents=True, exist_ok=True)
        self.spend_file.write_text(json.dumps({"usd": self.spent() + cost}))
        return cost

    # --- guards --------------------------------------------------------
    def _allowed(self, provider: str) -> bool:
        t = self.now()
        if self.open_until.get(provider, 0) > t:
            self.stats["skipped_open"] += 1
            return False
        q, w = self.quotas.get(provider), self.window[provider]
        while w and w[0] < t - 86400:
            w.popleft()
        if q and (len(w) >= q["rpd"] or sum(1 for x in w if x > t - 60) >= q["rpm"]):
            self.stats["skipped_quota"] += 1
            return False
        return True

    def call(self, tier: str, messages: list[dict], max_tokens: int = 1024, **kw) -> Completion:
        chain = list(self.tiers[tier])
        if tier != "judge" and self._openai_ready():
            chain.append(("openai", os.environ["OPENAI_MODEL"]))
        errors = []
        for i, (prov, model) in enumerate(chain):
            if not self._allowed(prov):
                continue
            extra = {"reasoning_effort": "low"} if "gpt-oss" in model else {}
            self.window[prov].append(self.now())
            t0 = time.perf_counter()
            try:
                c = self.client(prov, model).complete(messages, max_tokens=max_tokens, **extra, **kw)
            except ProviderError as e:
                if self.on_call:
                    self.on_call(provider=prov, tier=tier, ok=False, seconds=time.perf_counter() - t0)
                self.stats["errors"] += 1
                self.fail[prov] += 1
                if self.fail[prov] >= self.threshold:
                    self.open_until[prov] = self.now() + self.cooldown
                errors.append(str(e)[:100])
                continue
            self.fail[prov] = 0
            self.stats["calls"] += 1
            self.stats["by_provider"][prov] += 1
            self.stats["fallbacks"] += i > 0
            cost = self._charge(c) if prov == "openai" else 0.0
            self.stats["cost_usd"] += cost
            if self.on_call:
                self.on_call(provider=prov, tier=tier, ok=True, seconds=time.perf_counter() - t0, prompt=c.prompt_tokens, completion=c.completion_tokens, fallback=i > 0, cost=cost)
            return c
        raise ProviderError("router", None, f"all providers failed or skipped for tier {tier}: " + "; ".join(errors))
