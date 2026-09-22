"""Smoke tests that run without a database or API keys.

They exercise the pure-Python pieces (config, chunker) and confirm the FastAPI
app builds and its health route works, so CI catches import/wiring breakage.
"""
from __future__ import annotations

import os

# Ensure imports that read settings don't fail for missing secrets.
os.environ.setdefault("GEMINI_API_KEY", "test-key")

from config import get_settings  # noqa: E402
from ingestion.chunker import chunk_text  # noqa: E402


def test_settings_database_url():
    url = get_settings().database_url
    assert url.startswith("postgresql+psycopg2://")


def test_chunker_splits_and_overlaps():
    text = ("Sentence about revenue. " * 400).strip()
    chunks = chunk_text(text)
    assert len(chunks) > 1
    assert all(chunks)
    # No chunk should be wildly larger than the configured size (+ overlap).
    limit = get_settings().chunk_size + get_settings().chunk_overlap + 50
    assert max(len(c) for c in chunks) <= limit


def test_health_route():
    # Import here so a failure surfaces as a test, not a collection error.
    import app as app_module

    # Don't trigger the DB-initialising lifespan; call the router directly.
    from routes.health import health_check

    assert health_check() == {"status": "healthy"}
    assert app_module.app.title.startswith("AI-Powered Investor Intelligence")
