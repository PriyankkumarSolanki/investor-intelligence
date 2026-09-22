"""Embedding provider abstraction.

Default: Google Gemini `gemini-embedding-001` (768-dim requested, free tier, no
local compute). Alternative: local sentence-transformers (fully offline,
384-dim). The reference project used Azure OpenAI embeddings; swapping providers
here is the open-stack equivalent.
"""
from __future__ import annotations

import time
from functools import lru_cache

from config import get_settings


class GeminiEmbeddings:
    """Embeddings via Google Generative AI (gemini-embedding-001).

    gemini-embedding-001 embeds one input per request, and the free tier caps
    requests at ~100/minute. We pace requests under a configurable RPM and retry
    on 429 using the server-suggested delay.
    """

    def __init__(self, api_key: str, model: str, dim: int, max_rpm: int) -> None:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        self._genai = genai
        self.model = model
        self.dim = dim
        self.min_interval = 60.0 / max_rpm if max_rpm > 0 else 0.0
        self._last_call = 0.0

    def _throttle(self) -> None:
        if self.min_interval <= 0:
            return
        wait = self.min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.monotonic()

    def _embed(self, text: str, task_type: str, retries: int = 5) -> list[float]:
        from google.api_core.exceptions import ResourceExhausted

        for attempt in range(retries):
            self._throttle()
            try:
                result = self._genai.embed_content(
                    model=self.model,
                    content=text,
                    task_type=task_type,
                    output_dimensionality=self.dim,
                )
                return result["embedding"]
            except ResourceExhausted as exc:
                if attempt == retries - 1:
                    raise
                delay = getattr(exc, "retry_delay", None)
                seconds = getattr(delay, "seconds", 0) or 0
                time.sleep(max(seconds + 1, 2 ** attempt))
        raise RuntimeError("unreachable")

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text, "retrieval_query")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t, "retrieval_document") for t in texts]


class LocalEmbeddings:
    """Fully offline embeddings via fastembed (ONNX, no torch, no quota).

    Default model BAAI/bge-small-en-v1.5 -> 384-dim. The model (~130 MB) is
    downloaded once on first use and cached.
    """

    def __init__(self, model_name: str) -> None:
        from fastembed import TextEmbedding

        self.model = TextEmbedding(model_name=model_name)

    def embed_query(self, text: str) -> list[float]:
        return next(iter(self.model.query_embed(text))).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [vec.tolist() for vec in self.model.passage_embed(texts)]


@lru_cache
def get_embeddings():
    """Return the configured embedding provider (cached singleton)."""
    settings = get_settings()

    if settings.embedding_provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to .env or switch "
                "EMBEDDING_PROVIDER=local."
            )
        return GeminiEmbeddings(
            api_key=settings.gemini_api_key,
            model=settings.gemini_embed_model,
            dim=settings.embedding_dim,
            max_rpm=settings.embed_max_rpm,
        )

    if settings.embedding_provider == "local":
        return LocalEmbeddings(settings.local_embed_model)

    raise ValueError(f"Unknown embedding_provider: {settings.embedding_provider!r}")
