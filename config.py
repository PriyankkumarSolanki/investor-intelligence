"""Central configuration, loaded from environment / .env.

Every knob that differs between the free local stack and an Azure production
deployment lives here, so switching providers is a config change rather than a
code change. This is the open-stack counterpart to the reference project's
config/settings.yaml + Azure environment variables.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database (Postgres + pgvector) ----------------------------------
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "investor"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"

    # --- LLM provider -----------------------------------------------------
    # "gemini" now; the llm/ package leaves room for an "azure" provider later.
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-lite-latest"

    # --- Embedding provider ----------------------------------------------
    # "local" (default) uses fastembed — no API quota, ideal for ingesting large
    # filings on a free tier. "gemini" uses the API (100 req/min, low daily cap;
    # only practical for small documents).
    embedding_provider: str = "local"
    gemini_embed_model: str = "models/gemini-embedding-001"
    local_embed_model: str = "BAAI/bge-small-en-v1.5"
    # Output size of the embedding vectors. Must match the provider/model:
    #   bge-small-en-v1.5 -> 384; gemini-embedding-001 -> configurable (e.g. 768).
    # Changing this requires recreating the chunks table (the vector column is
    # typed to this size).
    embedding_dim: int = 384

    # --- RAG / chunking ---------------------------------------------------
    # Larger chunks -> fewer embedding calls (important on the free tier, which
    # caps embeddings at ~100 requests/minute).
    chunk_size: int = 2200        # characters per chunk (markdown-aware splitter)
    chunk_overlap: int = 200
    retrieval_top_k: int = 8

    # Free-tier embeddings allow 100 requests/minute; stay safely under it.
    embed_max_rpm: int = 90

    # --- Storage ----------------------------------------------------------
    raw_pdf_dir: str = "data/raw_pdfs"
    markdown_dir: str = "data/markdown"
    max_upload_mb: int = 50

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
