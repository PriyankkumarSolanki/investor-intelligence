"""Convert PDF reports to Markdown, preserving tables (via pymupdf4llm).

Markdown keeps the tabular structure of financial statements, which plain text
would destroy — the same rationale the reference project gives.
"""
from __future__ import annotations

from pathlib import Path

import pymupdf4llm


def convert_pdf(pdf_path: str, output_dir: str) -> str:
    """Convert one PDF to a Markdown file; return the markdown path."""
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    markdown = pymupdf4llm.to_markdown(str(pdf_file))
    markdown_file = out_dir / f"{pdf_file.stem}.md"
    markdown_file.write_text(markdown, encoding="utf-8")
    return str(markdown_file)
