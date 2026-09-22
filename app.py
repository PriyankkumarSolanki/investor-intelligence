"""FastAPI application entry point.

Open-stack counterpart to the reference app.py. On startup it initialises the
Postgres schema (pgvector extension + tables). The UI is a separate Streamlit
service (frontend/streamlit_app.py) that talks to this API.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from database.db import init_db
from routes.chat import router as chat_router
from routes.dashboard import router as dashboard_router
from routes.health import router as health_router
from routes.ingestion import router as ingestion_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AI-Powered Investor Intelligence Platform (open stack)",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(health_router, tags=["Health"])
app.include_router(ingestion_router, prefix="/api", tags=["Ingestion"])
app.include_router(chat_router, prefix="/api", tags=["Chat"])
app.include_router(dashboard_router, prefix="/api", tags=["Dashboard"])


@app.get("/")
def root():
    return {
        "service": "investor-intelligence",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
