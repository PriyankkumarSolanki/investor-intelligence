"""KPI metrics endpoint consumed by the Streamlit dashboard."""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from database.db import get_engine
from database.metrics import get_metrics

router = APIRouter()


@router.get("/metrics")
def metrics():
    return get_metrics()


@router.get("/ingested")
def ingested():
    """Distinct company/year that have chunks stored (may not have KPIs yet)."""
    with get_engine().connect() as conn:
        rows = conn.execute(
            text(
                "SELECT company, year, count(*) AS chunks "
                "FROM chunks GROUP BY company, year ORDER BY company"
            )
        )
        return [dict(r._mapping) for r in rows]


@router.get("/companies")
def companies():
    rows = get_metrics()
    seen = sorted({r["company"] for r in rows if r.get("company")})
    return {"companies": seen}
