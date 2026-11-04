"""Heading-aware markdown chunking."""
from __future__ import annotations

import re
from dataclasses import dataclass

MAX_WORDS = 180

_INCLUDE = re.compile(r"^\{\*.*\*\}\s*$")  # mkdocs code-include directives, not prose
_FENCE_MARK = re.compile(r"^/{3,}.*$")  # admonition fences: "/// note" and closing "///"
_HEADING = re.compile(r"^(#{1,4})\s+(.*?)(\s*\{#.*\})?\s*$")


@dataclass
class Chunk:
    id: int
    doc: str
    heading: str
    text: str


def clean(markdown: str) -> list[str]:
    """Drop front matter, include directives and admonition fences; keep the prose and code fences."""
    lines = markdown.splitlines()
    if lines and lines[0].strip() == "---":
        end = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == "---"), 0)
        lines = lines[end + 1 :]
    out = []
    for line in lines:
        if _INCLUDE.match(line.strip()) or _FENCE_MARK.match(line.strip()):
            continue
        out.append(line)
    return out


def split_sections(markdown: str) -> list[tuple[str, list[str]]]:
    """Split on headings (code fences respected). Returns (heading path, body lines) per section."""
    sections: list[tuple[str, list[str]]] = []
    path: list[str] = []
    buf: list[str] = []
    in_code = False

    def flush() -> None:
        if any(l.strip() for l in buf):
            sections.append((" > ".join(path), buf.copy()))
        buf.clear()

    for line in clean(markdown):
        if line.strip().startswith("```"):
            in_code = not in_code
        m = None if in_code else _HEADING.match(line)
        if m:
            flush()
            level = len(m.group(1))
            path[:] = path[: level - 1] + [m.group(2).strip()]
        else:
            buf.append(line)
    flush()
    return sections


def chunk_markdown(doc: str, markdown: str, start_id: int = 0, max_words: int = MAX_WORDS) -> list[Chunk]:
    """Split on headings, then pack paragraphs up to max_words. Heading path is kept as context."""
    sections = split_sections(markdown)

    chunks: list[Chunk] = []
    cid = start_id
    for heading, lines in sections:
        paras, cur = [], []
        for line in lines:
            if line.strip() == "" and cur:
                paras.append("\n".join(cur)); cur = []
            elif line.strip() != "":
                cur.append(line)
        if cur:
            paras.append("\n".join(cur))
        acc, words = [], 0
        for p in paras:
            w = len(p.split())
            if acc and words + w > max_words:
                chunks.append(Chunk(cid, doc, heading, "\n\n".join(acc))); cid += 1
                acc, words = [], 0
            acc.append(p); words += w
        if acc:
            chunks.append(Chunk(cid, doc, heading, "\n\n".join(acc))); cid += 1
    return chunks
