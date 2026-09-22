"""Persist extracted KPIs to Postgres (mirrors reference database/save_metrics.py)."""
from __future__ import annotations

from sqlalchemy import text

from database.db import get_engine

_INSERT = """
INSERT INTO financial_metrics (
    company, year, revenue, net_income, operating_income, cash_flow,
    total_assets, total_liabilities, risk_factors, growth_drivers
) VALUES (
    :company, :year, :revenue, :net_income, :operating_income, :cash_flow,
    :total_assets, :total_liabilities, :risk_factors, :growth_drivers
)
"""


def _join(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return "\n".join(str(v) for v in value)
    return str(value)


def save_metrics(company: str, year: int | str | None, metrics: dict) -> None:
    """Insert one KPI row. `metrics` uses the FinancialMetrics field names."""
    params = {
        "company": company,
        "year": str(year) if year is not None else None,
        "revenue": _join(metrics.get("revenue")),
        "net_income": _join(metrics.get("net_income")),
        "operating_income": _join(metrics.get("operating_income")),
        "cash_flow": _join(metrics.get("cash_flow")),
        "total_assets": _join(metrics.get("total_assets")),
        "total_liabilities": _join(metrics.get("total_liabilities")),
        "risk_factors": _join(metrics.get("risk_factors")),
        "growth_drivers": _join(metrics.get("growth_drivers")),
    }
    with get_engine().begin() as conn:
        conn.execute(text(_INSERT), params)
