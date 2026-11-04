"""3.2 Exact and semantic answer cache. A hit skips retrieval and every LLM call.

namespace ties entries to the corpus and prompt version, so a re-index or prompt change cannot serve stale answers.
The semantic threshold is tuned in scripts/tune_cache.py; a wrong hit (similar question, different answer) is worse than a miss.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable

import numpy as np


def normalise(q: str) -> str:
    return " ".join(re.findall(r"\w+", q.lower()))


@dataclass
class Entry:
    question: str
    vec: np.ndarray | None
    value: dict
    ts: float


class Cache:
    def __init__(self, embed: Callable[[str], np.ndarray] | None = None, threshold: float = 0.9, ttl_s: float = 86400.0, namespace: str = "",
                 now: Callable[[], float] = time.time):
        self.embed, self.threshold, self.ttl, self.ns, self.now = embed, threshold, ttl_s, namespace, now
        self.exact: dict[str, Entry] = {}
        self.stats = {"exact": 0, "semantic": 0, "miss": 0}

    def _live(self, e: Entry) -> bool:
        return self.now() - e.ts <= self.ttl

    def get(self, question: str) -> tuple[dict | None, str | None, float]:
        """Returns (value, kind, similarity). kind is 'exact', 'semantic' or None."""
        e = self.exact.get(self.ns + normalise(question))
        if e and self._live(e):
            self.stats["exact"] += 1
            return e.value, "exact", 1.0
        if self.embed and self.exact:
            q = self.embed(question)
            live = [(k, x) for k, x in self.exact.items() if k.startswith(self.ns) and x.vec is not None and self._live(x)]
            if live:
                sims = np.array([x.vec for _, x in live]) @ q
                i = int(np.argmax(sims))
                if sims[i] >= self.threshold:
                    self.stats["semantic"] += 1
                    return live[i][1].value, "semantic", float(sims[i])
        self.stats["miss"] += 1
        return None, None, 0.0

    def put(self, question: str, value: dict) -> None:
        self.exact[self.ns + normalise(question)] = Entry(question, self.embed(question) if self.embed else None, value, self.now())

    @property
    def hit_rate(self) -> float:
        n = sum(self.stats.values())
        return (self.stats["exact"] + self.stats["semantic"]) / n if n else 0.0
