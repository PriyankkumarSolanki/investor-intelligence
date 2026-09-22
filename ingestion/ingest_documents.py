"""End-to-end ingestion of a single report (mirrors reference ingest_documents.py).

PDF -> Markdown -> chunk -> embed+store (pgvector) -> RAG KPI extraction ->
persist KPIs to Postgres.
"""
from __future__ import annotations

from pathlib import Path

from config import get_settings
from database.save_metrics import save_metrics
from ingestion.chunker import chunk_markdown_file
from ingestion.pdf_to_markdown import convert_pdf
from rag.kpi_extractor import extract_financial_metrics
from vectorstore.pgvector_store import PgVectorStore, Retriever


def parse_company_year(pdf_file: Path) -> tuple[str, str]:
    """Parse company and year from names like `2024_Apple.pdf`."""
    parts = pdf_file.stem.split("_")
    if parts and parts[0].isdigit():
        return parts[-1], parts[0]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return pdf_file.stem, ""


def ingest_document(pdf_path: str) -> dict:
    """Ingest one PDF.

    Storage (PDF -> markdown -> chunk -> embed -> pgvector) uses the local
    embedder and always runs. KPI extraction calls the LLM, which is rate-limited
    on the free tier; if it fails we still return success with the chunks stored,
    so the document is searchable and KPIs can be generated later via
    `extract_and_save`.
    """
    settings = get_settings()
    pdf_file = Path(pdf_path)
    company, year = parse_company_year(pdf_file)
    year_int = int(year) if year.isdigit() else None

    markdown_file = convert_pdf(pdf_path, settings.markdown_dir)
    chunks = chunk_markdown_file(markdown_file)

    store = PgVectorStore()
    # Idempotent: replace any previously-ingested chunks for this company/year.
    store.delete_company(company, year)
    stored = store.upload_chunks(
        chunks=chunks,
        company=company,
        year=year,
        source_file=pdf_file.name,
    )

    metrics, metrics_error = None, None
    try:
        metrics = extract_and_save(company, year_int, store=store)
    except Exception as exc:  # keep the stored chunks; surface a soft error
        metrics_error = str(exc)

    return {
        "company": company,
        "year": year,
        "chunks_stored": stored,
        "metrics": metrics,
        "metrics_error": metrics_error,
    }


def extract_and_save(
    company: str,
    year: int | None,
    store: PgVectorStore | None = None,
) -> dict:
    """Run KPI extraction against already-stored chunks and persist the result."""
    store = store or PgVectorStore()
    metrics = extract_financial_metrics(
        retriever=Retriever(store),
        company=company,
        year=year,
    )
    if metrics:
        save_metrics(company=company, year=year, metrics=metrics)
    return metrics


def ingest_directory(input_dir: str) -> list[dict]:
    return [ingest_document(str(p)) for p in Path(input_dir).glob("*.pdf")]


if __name__ == "__main__":
    from database.db import init_db

    init_db()
    results = ingest_directory(get_settings().raw_pdf_dir)
    for r in results:
        print(f"{r['company']} {r['year']}: {r['chunks_stored']} chunks")
