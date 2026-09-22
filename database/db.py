"""Postgres engine and schema initialisation.

Open-stack counterpart to the reference's database/postgres_sql.py +
create_table.py. Docker Compose provisions the database itself, so we only need
to enable pgvector and create our two tables:
  - chunks            : embedded document chunks (vector store lives in Postgres)
  - financial_metrics : the extracted KPIs served to the dashboard
"""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.database_url, pool_pre_ping=True)


def init_db() -> None:
    """Enable pgvector and create tables if they don't exist."""
    settings = get_settings()
    engine = get_engine()

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS chunks (
                    id            BIGSERIAL PRIMARY KEY,
                    company       VARCHAR(100),
                    year          VARCHAR(10),
                    source_file   VARCHAR(255),
                    content       TEXT,
                    embedding     vector({settings.embedding_dim})
                )
                """
            )
        )
        # Approximate-nearest-neighbour index for cosine distance.
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS chunks_embedding_idx "
                "ON chunks USING hnsw (embedding vector_cosine_ops)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS chunks_company_year_idx "
                "ON chunks (company, year)"
            )
        )

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS financial_metrics (
                    id                 SERIAL PRIMARY KEY,
                    company            VARCHAR(100),
                    year               VARCHAR(10),
                    revenue            TEXT,
                    net_income         TEXT,
                    operating_income   TEXT,
                    cash_flow          TEXT,
                    total_assets       TEXT,
                    total_liabilities  TEXT,
                    risk_factors       TEXT,
                    growth_drivers     TEXT,
                    created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
