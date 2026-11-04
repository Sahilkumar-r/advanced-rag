"""Regression gate (docs/EVALS.md section 9): flag a run when a core metric is worse than the last good run by more than a tolerance.

Tolerances are placeholders (3 points on retrieval metrics) until enough runs show real noise. A metric that is missing from the new run
counts as a regression: a gate that passes because the number vanished is worse than no gate.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Finding:
    metric: str
    base: float | None
    new: float | None
    tolerance: float
    higher_is_better: bool
    regressed: bool
    note: str = ""

    @property
    def delta(self) -> float | None:
        return None if self.base is None or self.new is None else self.new - self.base


def get(d: dict, path: str):
    for k in path.split("."):
        d = d[k]
    return d


def compare(new: dict, base: dict, checks: list[tuple[str, float, bool]]) -> list[Finding]:
    """checks: (dotted path, tolerance, higher_is_better). Returns one Finding per check."""
    out = []
    for path, tol, higher in checks:
        try:
            b = float(get(base, path))
        except (KeyError, TypeError, ValueError):
            out.append(Finding(path, None, None, tol, higher, False, "no baseline for this metric: not gated"))
            continue
        try:
            n = float(get(new, path))
        except (KeyError, TypeError, ValueError):
            out.append(Finding(path, b, None, tol, higher, True, "missing from the new run"))
            continue
        worse_by = (b - n) if higher else (n - b)
        out.append(Finding(path, b, n, tol, higher, worse_by > tol + 1e-12))
    return out


def render(findings: list[Finding]) -> str:
    rows = ["metric | last good | new | change | tolerance | result", "--- | --- | --- | --- | --- | ---"]
    for f in findings:
        fmt = lambda v: "n/a" if v is None else f"{v:.4f}"
        change = "n/a" if f.delta is None else f"{f.delta:+.4f}"
        rows.append(f"{f.metric} | {fmt(f.base)} | {fmt(f.new)} | {change} | {f.tolerance} ({'higher' if f.higher_is_better else 'lower'} is better) | " + ("REGRESSED " + f.note if f.regressed else ("ok " + f.note).strip()))
    return "\n".join(rows)
