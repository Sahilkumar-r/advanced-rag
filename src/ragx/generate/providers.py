"""2.1 Provider adapters. One OpenAI compatible client covers Groq, Cerebras, Gemini, OpenRouter and OpenAI.

A mock provider is used by tests. Responses can be cached on disk so eval re-runs do not burn free quota.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import httpx

from ragx.config import PROVIDERS, ROOT, load_env

CACHE_DIR = ROOT / "data" / "cache" / "llm"


class ProviderError(Exception):
    def __init__(self, provider: str, status: int | None, message: str):
        super().__init__(f"{provider} {status}: {message}")
        self.provider, self.status = provider, status


@dataclass
class Completion:
    text: str
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    cached: bool = False


class OpenAICompat:
    def __init__(self, provider: str, model: str, cache: bool = True, timeout: float = 90):
        load_env()
        self.provider, self.model, self.cache, self.timeout = provider, model, cache, timeout
        self.base, key_var = PROVIDERS[provider]
        self.key = os.environ.get(key_var, "")

    def _cache_path(self, payload: dict) -> Path:
        h = hashlib.sha256(json.dumps([self.provider, payload], sort_keys=True).encode()).hexdigest()
        return CACHE_DIR / f"{h}.json"

    def complete(self, messages: list[dict], max_tokens: int = 1024, temperature: float = 0.0, **extra) -> Completion:
        if not self.key:
            raise ProviderError(self.provider, None, "no API key configured")
        payload = {"model": self.model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature, **extra}
        path = self._cache_path(payload)
        if self.cache and path.exists():
            return Completion(**json.loads(path.read_text(encoding="utf-8")) | {"cached": True})
        t = time.perf_counter()
        for attempt in range(3):  # a 429 usually clears in seconds on free tiers; the router (phase 3) owns real fallback
            try:
                r = httpx.post(f"{self.base}/chat/completions", json=payload, headers={"Authorization": f"Bearer {self.key}"}, timeout=self.timeout)
            except httpx.HTTPError as e:  # timeouts and connection errors become ProviderError so call_tier can fall back
                if attempt < 2:
                    continue
                raise ProviderError(self.provider, None, type(e).__name__) from e
            if r.status_code in (429, 503) and attempt < 2:
                time.sleep(min(float(r.headers.get("retry-after", 5)), 30))
                continue
            break
        if not r.is_success:
            raise ProviderError(self.provider, r.status_code, r.text[:200])
        d = r.json()
        u = d.get("usage") or {}
        out = Completion((d["choices"][0]["message"].get("content") or "").strip(), self.provider, self.model,
                         u.get("prompt_tokens", 0), u.get("completion_tokens", 0), (time.perf_counter() - t) * 1000)
        if self.cache:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({k: getattr(out, k) for k in ("text", "provider", "model", "prompt_tokens", "completion_tokens", "latency_ms")}), encoding="utf-8")
        return out


def call_tier(tier: str, messages: list[dict], max_tokens: int = 1024, **kw) -> Completion:
    """Try each (provider, model) of a tier in order. A stand in for the phase 3 router (no breaker, no quotas)."""
    from ragx.config import TIERS

    errors = []
    for prov, model in TIERS[tier]:
        extra = {"reasoning_effort": "low"} if "gpt-oss" in model else {}  # keep reasoning tokens from eating the budget
        try:
            return OpenAICompat(prov, model).complete(messages, max_tokens=max_tokens, **extra, **kw)
        except ProviderError as e:
            errors.append(str(e)[:120])
    raise ProviderError("all", None, "; ".join(errors))


class Mock:
    """Scripted provider for tests: fn(messages) -> text."""

    provider, model = "mock", "mock"

    def __init__(self, fn: Callable[[list[dict]], str]):
        self.fn = fn
        self.calls: list[list[dict]] = []

    def complete(self, messages: list[dict], **_) -> Completion:
        self.calls.append(messages)
        text = self.fn(messages)
        return Completion(text, "mock", "mock", sum(len(m["content"].split()) for m in messages), len(text.split()))
