"""Upload + ingest endpoint (mirrors reference routes/ingestion.py)."""
from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from config import get_settings
from ingestion.ingest_documents import extract_and_save, ingest_document

router = APIRouter()


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    settings = get_settings()
    upload_dir = Path(settings.raw_pdf_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / file.filename

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Storage (local embeddings) must succeed; a rate-limited LLM extraction
        # does not fail the upload — it returns metrics_error instead.
        result = ingest_document(str(file_path))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}")

    if result.get("metrics_error"):
        message = (
            f"Stored {result['chunks_stored']} chunks for {result['company']} "
            f"{result['year']}. KPI extraction was rate-limited — click "
            f"'Generate KPIs' to retry (the document is already searchable)."
        )
    else:
        message = (
            f"Ingested {result['company']} {result['year']} — "
            f"{result['chunks_stored']} chunks stored and KPIs extracted."
        )
    return {"message": message, "file_name": file.filename, **result}


class ExtractRequest(BaseModel):
    company: str
    year: int | None = None


@router.post("/extract")
async def extract(request: ExtractRequest):
    """(Re)run KPI extraction for a company from already-stored chunks.

    Cheap: a single LLM call, so it works within the free-tier per-minute limit.
    """
    try:
        metrics = extract_and_save(request.company, request.year)
        return {"company": request.company, "year": request.year, "metrics": metrics}
    except Exception as exc:
        raise HTTPException(status_code=429, detail=f"Extraction failed: {exc}")
