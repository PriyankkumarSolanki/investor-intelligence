"""AI analyst chat endpoint (mirrors reference routes/chat.py)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from llm.gemini import generate_text
from vectorstore.pgvector_store import Retriever

router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    company: str | None = None
    year: int | None = None


@router.post("/chat")
async def chat(request: ChatRequest):
    try:
        retriever = Retriever()
        docs = retriever.invoke(
            query=request.question,
            company=request.company,
            year=request.year,
        )
        context = "\n\n".join(doc.page_content for doc in docs)

        prompt = (
            "Use the following context from corporate annual reports to answer "
            "the user's question. If the context does not contain relevant "
            "information, say you do not have enough data.\n\n"
            f"Context:\n{context}\n\n"
            f"User Question: {request.question}\n\nAnswer:"
        )
        answer = generate_text(prompt)
        return {"answer": answer}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
