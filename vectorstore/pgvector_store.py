"""pgvector-backed vector store.

Open-stack replacement for the reference project's vectorstore/azure_ai_search.py.
Chunks and their embeddings live in the same Postgres instance as the KPIs, so
there is no separate vector database to run. Cosine distance (`<=>`) with an HNSW
index provides approximate nearest-neighbour retrieval.
"""
from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import text

from database.db import get_engine
from embeddings.provider import get_embeddings


def _to_vector_literal(vec: list[float]) -> str:
    """pgvector accepts the text form '[0.1,0.2,...]'."""
    return "[" + ",".join(f"{x:.8f}" for x in vec) + "]"


class PgVectorStore:
    """Store and retrieve embedded chunks in Postgres."""

    def __init__(self) -> None:
        self.engine = get_engine()
        self.embeddings = get_embeddings()

    def delete_company(self, company: str, year: str | int | None) -> int:
        """Remove existing chunks for a company/year so re-ingest is idempotent."""
        where = "company = :company"
        params: dict = {"company": company}
        if year is not None and str(year) != "":
            where += " AND year = :year"
            params["year"] = str(year)
        with self.engine.begin() as conn:
            result = conn.execute(
                text(f"DELETE FROM chunks WHERE {where}"), params
            )
            return result.rowcount or 0

    def upload_chunks(
        self,
        chunks: list[str],
        company: str,
        year: str,
        source_file: str,
    ) -> int:
        """Embed and insert chunk texts. Returns the number stored."""
        if not chunks:
            return 0

        vectors = self.embeddings.embed_documents(chunks)

        rows = [
            {
                "company": company,
                "year": year,
                "source_file": source_file,
                "content": content,
                "embedding": _to_vector_literal(vector),
            }
            for content, vector in zip(chunks, vectors)
        ]

        stmt = text(
            """
            INSERT INTO chunks (company, year, source_file, content, embedding)
            VALUES (:company, :year, :source_file, :content, CAST(:embedding AS vector))
            """
        )
        with self.engine.begin() as conn:
            conn.execute(stmt, rows)
        return len(rows)


class Retriever:
    """Similarity search over the chunks table (mirrors reference Retriever)."""

    def __init__(self, store: PgVectorStore | None = None) -> None:
        self.store = store or PgVectorStore()

    def keyword_search(
        self,
        phrases: list[str],
        company: str | None = None,
        year: int | str | None = None,
        per_phrase: int = 2,
    ) -> list[SimpleNamespace]:
        """Lexical lookup for exact statement line-labels (e.g. 'Total assets').

        Vector search matches natural language poorly against number-heavy
        financial tables; this guarantees those chunks are in the context.
        """
        base = "company = :company"
        cbase: dict = {}
        if company:
            cbase["company"] = company
            if year is not None:
                base += " AND year = :year"
                cbase["year"] = str(year)
        else:
            base = "TRUE"

        out: list[SimpleNamespace] = []
        with self.store.engine.connect() as conn:
            for phrase in phrases:
                params = {**cbase, "pat": f"%{phrase}%", "lim": per_phrase}
                rows = conn.execute(
                    text(
                        f"SELECT content FROM chunks WHERE {base} "
                        "AND content ILIKE :pat LIMIT :lim"
                    ),
                    params,
                )
                out.extend(SimpleNamespace(page_content=r[0]) for r in rows)
        return out

    def invoke(
        self,
        query: str,
        company: str | None = None,
        year: int | str | None = None,
        top_k: int = 8,
    ) -> list[SimpleNamespace]:
        qvec = _to_vector_literal(self.store.embeddings.embed_query(query))

        where = ""
        params: dict = {"qvec": qvec, "top_k": top_k}
        if company:
            where = "WHERE company = :company"
            params["company"] = company
            if year is not None:
                where += " AND year = :year"
                params["year"] = str(year)

        stmt = text(
            f"""
            SELECT content
            FROM chunks
            {where}
            ORDER BY embedding <=> CAST(:qvec AS vector)
            LIMIT :top_k
            """
        )
        with self.store.engine.connect() as conn:
            result = conn.execute(stmt, params)
            return [SimpleNamespace(page_content=row[0]) for row in result]
