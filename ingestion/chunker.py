"""Markdown-aware recursive chunker.

The reference project uses LangChain's SemanticChunker, which embeds every
sentence — expensive and rate-limited on a free tier. We use a lightweight
recursive splitter that respects markdown structure (headings, then paragraphs,
then lines) and applies character overlap. It has no heavy dependencies and is
swappable behind the same interface.
"""
from __future__ import annotations

from pathlib import Path

from config import get_settings

# Try progressively finer separators so chunks fall on natural boundaries.
_SEPARATORS = ["\n## ", "\n### ", "\n#### ", "\n\n", "\n", ". ", " "]


def _split_recursive(chunk_text: str, separators: list[str], size: int) -> list[str]:
    if len(chunk_text) <= size:
        return [chunk_text]
    if not separators:
        # No separators left: hard-split by size.
        return [chunk_text[i : i + size] for i in range(0, len(chunk_text), size)]

    sep, *rest = separators
    parts = chunk_text.split(sep)
    out: list[str] = []
    buf = ""
    for part in parts:
        candidate = part if not buf else buf + sep + part
        if len(candidate) <= size:
            buf = candidate
        else:
            if buf:
                out.append(buf)
            if len(part) > size:
                out.extend(_split_recursive(part, rest, size))
                buf = ""
            else:
                buf = part
    if buf:
        out.append(buf)
    return out


def _apply_overlap(chunks: list[str], overlap: int) -> list[str]:
    if overlap <= 0 or len(chunks) <= 1:
        return chunks
    out = [chunks[0]]
    for i in range(1, len(chunks)):
        tail = chunks[i - 1][-overlap:]
        out.append(f"{tail} {chunks[i]}".strip())
    return out


def chunk_text(content: str) -> list[str]:
    """Split raw markdown/text into overlapping chunks."""
    settings = get_settings()
    raw = _split_recursive(content, _SEPARATORS, settings.chunk_size)
    cleaned = [c.strip() for c in raw if c and c.strip()]
    return _apply_overlap(cleaned, settings.chunk_overlap)


def chunk_markdown_file(markdown_file: str) -> list[str]:
    return chunk_text(Path(markdown_file).read_text(encoding="utf-8"))
