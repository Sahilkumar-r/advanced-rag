"""4.2 Guardrails: input (injection, PII and secrets, length), retrieval (injected chunks), output (citations, leaks).

Rule based so they run in CI without an LLM. They are heuristics: the safety eval (scripts/run_safety_eval.py)
reports what they miss and what benign questions they wrongly block.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Callable

INJECTION = [re.compile(p, re.I) for p in (
    r"\b(ignore|disregard|forget|override)\b[^.\n]{0,25}\b(previous|prior|above|earlier|all|your|these)\b[^.\n]{0,25}\b(instructions?|prompts?|rules?|guidelines?|system)\b",
    r"\b(ignore|disregard|forget|override)\s+the\s+(system|previous|prior|above)\s+(prompt|instructions?|rules?|message|text)\b",
    r"\b(translate|paraphrase|summari[sz]e|print|write out)\b[^.\n]{0,20}\byour\b[^.\n]{0,12}\b(instructions?|prompt|rules)\b",
    r"\b(zero|no|without any)\s+(safety\s+)?(limits|restrictions|guardrails)\b",
    r"\b(reveal|show|print|repeat|leak|output|tell me)\b[^.\n]{0,25}\b(system|hidden|initial|original)\b[^.\n]{0,12}\b(prompt|instructions?|message)\b",
    r"\byou are now\b[^.\n]{0,30}\b(dan|unrestricted|unfiltered|jailbroken|developer mode|evil)\b",
    r"\b(jailbreak|do anything now)\b",
    r"\b(enter|enable|activate|switch to|in) developer mode\b",
    r"\bpretend\b[^.\n]{0,20}\b(you have no|you are not bound|there are no)\b[^.\n]{0,20}\b(rules|restrictions|limits)\b",
    r"<\|?(im_start|system|endoftext)\|?>",
    r"^\s*(#{1,3}\s*)?(system|assistant)\s*:\s",
    r"\b(begin|end)\s+(system|hidden)\s+prompt\b",
    r"\bnew instructions?\s*:",
)]
PII = {
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "api_key": re.compile(r"\b(sk-[A-Za-z0-9_-]{16,}|gsk_[A-Za-z0-9]{16,}|AIza[0-9A-Za-z_-]{20,}|hf_[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{16,}|csk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,})\b"),
    "jwt": re.compile(r"\beyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{8,}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "card": re.compile(r"\b(?:\d[ -]?){13,19}\b"),  # before phone: redaction must replace a card before the phone pattern sees it
    "phone": re.compile(r"(?<!\w)(?:\+\d{1,3}[\s.-]?)?\(?\d{2,4}\)?[\s.-]\d{3,4}[\s.-]\d{3,4}(?!\w)"),  # needs separators, so bare long ids do not match
}
MAX_CHARS = {"guest": 300, "default": 1000}


def _luhn(digits: str) -> bool:
    ds = [int(c) for c in digits][::-1]
    return sum(d if i % 2 == 0 else (d * 2 - 9 if d * 2 > 9 else d * 2) for i, d in enumerate(ds)) % 10 == 0


def _real(kind: str, match: str) -> bool:
    """Filter regex hits that are not really PII (a 15 digit number that fails Luhn, a short digit run)."""
    digits = re.sub(r"\D", "", match)
    if kind == "card":
        return 13 <= len(digits) <= 19 and _luhn(digits)
    if kind == "phone":
        return 9 <= len(digits) <= 15
    return True


def find_pii(text: str) -> list[str]:
    cards = [m.span() for m in PII["card"].finditer(text) if _real("card", m.group(0))]
    inside_card = lambda m: any(a <= m.start() and m.end() <= b for a, b in cards)  # a card number also looks like a phone number
    return [kind for kind, rx in PII.items() if any(_real(kind, m.group(0)) and not (kind == "phone" and inside_card(m)) for m in rx.finditer(text))]


def redact(text: str) -> str:
    for kind, rx in PII.items():
        text = rx.sub(lambda m, kind=kind: f"[REDACTED:{kind}]" if _real(kind, m.group(0)) else m.group(0), text)
    return text


_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"))


def _fold(text: str) -> str:
    """NFKC and no zero width characters, so look-alike and invisible character tricks do not slip past the patterns."""
    return unicodedata.normalize("NFKC", text).translate(_ZERO_WIDTH)


def is_injection(text: str) -> bool:
    folded = _fold(text)
    return any(rx.search(folded) for rx in INJECTION)


@dataclass
class Verdict:
    blocked: bool
    reason: str | None
    flags: list[str] = field(default_factory=list)
    text: str = ""


def check_input(text: str, role: str = "viewer", classifier: Callable[[str], bool] | None = None) -> Verdict:
    """Blocks too long input and injection. PII and secrets are redacted (not blocked) so they never reach a free tier LLM."""
    limit = MAX_CHARS["guest"] if role == "guest" else MAX_CHARS["default"]
    if len(text) > limit:
        return Verdict(True, "too_long", ["too_long"], text[:80])
    if is_injection(text) or (classifier is not None and classifier(text)):
        return Verdict(True, "prompt_injection", ["injection"], "")
    flags = [f"pii:{k}" for k in find_pii(text)]
    return Verdict(False, None, flags, redact(text) if flags else text)


def filter_children(children: list, flags: list[str] | None = None) -> list:
    """Retrieval guard: drop retrieved chunks that contain instructions aimed at the model."""
    kept = [c for c in children if not is_injection(c.text)]
    if flags is not None and len(kept) < len(children):
        flags.append(f"retrieved_injection:{len(children) - len(kept)}")
    return kept


@dataclass
class OutputVerdict:
    flags: list[str]
    text: str


def check_output(text: str, n_sources: int, refused: bool, source_text: str = "") -> OutputVerdict:
    """Flags answers without a resolvable [n] citation, and redacts PII or secrets that are not in the sources."""
    flags = []
    if not refused:
        cites = [int(c) for c in re.findall(r"\[(\d+)\]", text)]
        if not cites:
            flags.append("no_citation")
        elif any(not 1 <= c <= n_sources for c in cites):
            flags.append("bad_citation")
    in_sources = find_pii(source_text)
    leaked = [k for k in find_pii(text) if k not in in_sources]
    if leaked:
        flags += [f"leak:{k}" for k in leaked]
        text = redact(text)
    return OutputVerdict(flags, text)
