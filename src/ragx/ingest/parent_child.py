"""1.2 Parent child chunking. Parent = one heading section. Children = token budgeted windows inside it.

Children are what gets embedded and searched; the parent is what a generator will read (phase 2).
Tokens are counted with a regex (words and punctuation), a proxy for the embedder's tokenizer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .chunking import split_sections

_TOK = re.compile(r"\w+|[^\w\s]")


def ntok(text: str) -> int:
    return len(_TOK.findall(text))


@dataclass
class Parent:
    id: int
    doc: str
    heading: str
    text: str


@dataclass
class Child:
    id: int
    doc: str
    heading: str
    text: str
    parent: int


def _paragraphs(lines: list[str]) -> list[str]:
    paras, cur = [], []
    for line in lines:
        if line.strip() == "" and cur:
            paras.append("\n".join(cur))
            cur = []
        elif line.strip() != "":
            cur.append(line)
    if cur:
        paras.append("\n".join(cur))
    return paras


def _split_big(para: str, size: int) -> list[str]:
    """Split an oversize paragraph (usually a code block) on line breaks."""
    out, cur, n = [], [], 0
    for line in para.split("\n"):
        t = ntok(line)
        if cur and n + t > size:
            out.append("\n".join(cur))
            cur, n = [], 0
        cur.append(line)
        n += t
    out.append("\n".join(cur))
    return out  # shortcut: a single line longer than size stays whole; upgrade if the study shows it matters


def chunk_pages(pages: dict[str, str], size: int, overlap: float = 0.0) -> tuple[list[Parent], list[Child]]:
    """pages maps doc id to markdown. overlap is a fraction of size carried into the next child."""
    parents: list[Parent] = []
    children: list[Child] = []
    budget = int(size * overlap)
    for doc, md in pages.items():
        for heading, lines in split_sections(md):
            paras = _paragraphs(lines)
            parents.append(Parent(len(parents), doc, heading, "\n\n".join(paras)))
            pid = parents[-1].id
            units = [u for p in paras for u in (_split_big(p, size) if ntok(p) > size else [p])]
            acc: list[str] = []
            n = 0
            for u in units:
                t = ntok(u)
                if acc and n + t > size:
                    children.append(Child(len(children), doc, heading, "\n\n".join(acc), pid))
                    carry, c = [], 0
                    for a in reversed(acc):
                        if c + ntok(a) > budget:
                            break
                        carry.insert(0, a)
                        c += ntok(a)
                    acc, n = carry, c
                acc.append(u)
                n += t
            children.append(Child(len(children), doc, heading, "\n\n".join(acc), pid))
    return parents, children
