"""Read the latest KPI row per company/year (mirrors reference database/metrics.py)."""
from __future__ import annotations

from sqlalchemy import text

from database.db import get_engine

_LATEST_PER_COMPANY = """
SELECT id, company, year, revenue, net_income, operating_income, cash_flow,
       total_assets, total_liabilities, risk_factors, growth_drivers, created_at
FROM (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY company, year
               ORDER BY created_at DESC
           ) AS rn
    FROM financial_metrics
) t
WHERE rn = 1
ORDER BY company
"""


def get_metrics() -> list[dict]:
    with get_engine().connect() as conn:
        result = conn.execute(text(_LATEST_PER_COMPANY))
        return [dict(row._mapping) for row in result]
