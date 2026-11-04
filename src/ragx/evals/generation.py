"""2.4 LLM judge and generation metrics: faithfulness, answer relevancy, citation accuracy, refusal correctness.

The judge tier uses a different model family than the answer tier. Its agreement with labels is measured in
scripts/run_judge_calibration.py before any generation number is trusted.
"""
from __future__ import annotations

from ragx.generate.answer import LLM, Source, format_context
from ragx.selfrag.controller import parse_json

JUDGE_SYSTEM = (
    "You are a strict grader of answers about software documentation. You get numbered sources, a question and an answer.\n"
    "Count the distinct factual claims in the answer. A claim is supported only if the sources state it or directly imply it. "
    "General knowledge that is not in the sources counts as NOT supported.\n"
    "Reply with JSON only:\n"
    '{"total_claims": int, "supported_claims": int, "relevancy": "yes" | "partial" | "no" (does the answer address the question), '
    '"citations": [{"n": source number cited in the answer, "supports": true if that source supports the sentence citing it}]}'
)


def judge(question: str, sources: list[Source], answer: str, llm: LLM) -> dict:
    user = f"Sources:\n{format_context(sources)}\n\nQuestion: {question}\n\nAnswer:\n{answer}"
    c = llm("judge", [{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": user}], max_tokens=800)
    d = parse_json(c.text)
    d["_ok"] = isinstance(d.get("total_claims"), int) and isinstance(d.get("supported_claims"), int)
    return d


def faithful_label(d: dict) -> bool | None:
    """True when every claim is supported. None if the judge reply could not be parsed."""
    return None if not d.get("_ok") else d["supported_claims"] >= d["total_claims"]


def faithfulness(d: dict) -> float | None:
    return None if not d.get("_ok") or d["total_claims"] == 0 else d["supported_claims"] / d["total_claims"]


def relevancy(d: dict) -> float | None:
    return {"yes": 1.0, "partial": 0.5, "no": 0.0}.get(d.get("relevancy"))


def citation_accuracy(d: dict) -> float | None:
    cites = [c for c in d.get("citations", []) if isinstance(c, dict)]
    return sum(bool(c.get("supports")) for c in cites) / len(cites) if cites else None


def refusal_correct(kind: str, refused: bool) -> bool:
    """answerable questions must be answered; off topic and out of corpus questions must be refused."""
    return not refused if kind == "answerable" else refused
