# PROJECT HANDBOOK
## AI-Powered Investor Intelligence Platform (Open-Stack RAG)
**A complete technical, learning, and interview-preparation guide**

**Author:** Priyank · **Repository:** github.com/&lt;you&gt;/investor-intelligence
**Stack:** Python · FastAPI · Streamlit · Google Gemini · fastembed (bge-small) · pgvector · PostgreSQL · pymupdf4llm · Docker Compose · pytest · ruff · GitHub Actions · Kubernetes (phase 2)
**Difficulty:** Intermediate → Advanced · **Level:** Beginner-friendly explanations, production-grade content · **Version:** 1.0

---

## How to use this document

This is your single source of truth for the Investor Intelligence Platform. It does four jobs:

1. **Teaches the project from the ground up** — every module, every design decision, every technology, explained plainly.
2. **Prepares you for interviews** — 50+ questions with model answers, organised by difficulty and topic.
3. **Gives you talking points** — how to pitch this project in 30 seconds, 2 minutes, or 5 minutes.
4. **Serves as revision notes** — a condensed cheat-sheet at the end for the night before an interview.

Python knowledge is assumed. Retrieval-Augmented Generation (RAG), embeddings, vector databases, LLM APIs, and the containerised deployment lifecycle are all explained from first principles, because those are the parts an interviewer will actually probe.

**A word on honesty up front.** This project is a deliberate **open-stack rebuild** of an Azure-based tutorial (AaiTech's "AI-Powered Investor Intelligence Platform"). The *architecture* is faithful to the original; the *providers* were swapped for free, local equivalents so the whole thing runs at zero cost. That substitution is not a shortcut — it is the most interesting engineering in the project, and this handbook treats it as a first-class talking point.

**Boxes you will see throughout:**
> **Key Takeaway** — the one thing to remember from a section.
> **Common Pitfall** — a mistake people make, or a trap an interviewer might set.
> **Interview angle** — how this specific point tends to come up in interviews.

---

## Table of Contents

1. Executive Summary
2. The Problem: Why Extracting Financials from 10-Ks Is Hard
3. The Data: SEC 10-K Filings (and How We Got Them)
4. System Architecture
5. Concept Primer: Retrieval-Augmented Generation (RAG)
6. Concept Primer: Embeddings, Vector Search, and pgvector
7. Folder Structure, File by File
8. Code Walkthrough — Configuration (the free⇄Azure seam)
9. Code Walkthrough — Ingestion (PDF → Markdown → Chunk)
10. Code Walkthrough — Embeddings and the pgvector Store
11. Code Walkthrough — The LLM Provider (Gemini)
12. Code Walkthrough — RAG KPI Extraction (Hybrid Retrieval)
13. Code Walkthrough — The API (Routes and Decoupled Ingestion)
14. Code Walkthrough — The Streamlit UI
15. Every Design Decision, Justified
16. Results and How to Read Them
17. Testing Strategy
18. Docker, CI, and Reproducibility
19. Debugging Guide (Real Problems You Hit)
20. Production Readiness and Future Work
21. Interview Question Bank (50+ Q&A)
22. Resume Talking Points (30s / 2min / 5min)
23. Glossary
24. Final Revision Notes

---

## 1. Executive Summary

The Investor Intelligence Platform ingests a company's annual report (an SEC **Form 10-K**, typically 80–160 pages of PDF), extracts the key financial KPIs — revenue, net income, operating income, operating cash flow, total assets, total liabilities, plus top risk factors and growth drivers — and serves them on a comparison dashboard alongside an AI analyst chatbot that answers follow-up questions grounded in the filings.

Under the hood it is a **Retrieval-Augmented Generation (RAG)** system:

```
PDF ─▶ Markdown ─▶ chunk ─▶ embed ─▶ pgvector
                                        │
                     hybrid retrieval ◀─┘
                              │
                              ▼
              Gemini → structured JSON KPIs ─▶ Postgres ─▶ dashboard
                              │
              chat question → retrieve → Gemini → grounded answer
```

The headline engineering story is **provider substitution under real-world constraints**. The reference project uses Azure OpenAI, Azure AI Search, and Azure Kubernetes Service — all paid. This build swaps in **Google Gemini** (LLM), **fastembed** (local embeddings), **pgvector inside PostgreSQL** (vector store), and **Docker Compose** (local orchestration), so it runs free. Getting that to actually work on free-tier quotas forced several real design decisions — decoupling ingestion from extraction, hybrid retrieval, and local embeddings — that are the meat of this document.

> **Key Takeaway** — This is a production-shaped RAG application whose most valuable lessons come from making an expensive cloud architecture run on a free stack.

Verified result: four real 10-Ks (Apple FY2025, Microsoft FY2026, Tesla FY2025, Alphabet/Google FY2025) ingested and extracted with **zero blank KPI fields**.

---

## 2. The Problem: Why Extracting Financials from 10-Ks Is Hard

An investor comparing companies wants a handful of numbers and a sense of the risks. Those numbers live inside 100+ page regulatory filings. Three things make pulling them out hard:

1. **Scale and noise.** A 10-K is mostly prose — business description, risk factors, MD&A, legal proceedings — with the actual financial statements buried in the back. A naive "send the whole document to an LLM" approach blows the context window and buries the signal.
2. **Tables.** The numbers that matter (income statement, balance sheet, cash flow statement) are **tables**. Converting a PDF to plain text destroys table structure; you get a soup of numbers with no idea which figure is revenue and which is the prior-year comparative.
3. **Two-year columns.** Financial statements show the current *and* prior fiscal year side by side. "Total assets $ 450,256 $ 595,281" — which one do you want? Pick wrong and every downstream comparison is off by a year.

RAG addresses (1) by retrieving only the relevant slices. Markdown conversion addresses (2). And explicit prompt rules plus hybrid retrieval address (3) and the table-ranking problem (see §12 and §19).

> **Interview angle** — "Why not just fine-tune a model or dump the whole PDF into the prompt?" Answer: cost, context limits, and grounding/traceability. RAG retrieves a small, relevant, *citable* context and keeps the LLM honest.

---

## 3. The Data: SEC 10-K Filings (and How We Got Them)

The dataset is **authentic public filings**, not synthetic data. Every company files its 10-K with the U.S. Securities and Exchange Commission (SEC), and they are free on **EDGAR** (the SEC's filing system).

**How the sample reports were obtained (reproducible):**

1. Query EDGAR's JSON submissions API for a company's CIK (e.g. Apple = `0000320193`) to find the latest 10-K's primary document URL.
2. Download the filing's inline-XBRL HTML with a *declared* User-Agent (SEC blocks anonymous scripted access; the UA must contain contact info) and follow the redirect.
3. Render the HTML to PDF with headless Chrome (`--headless=new --print-to-pdf`), because our ingestion pipeline expects PDF.
4. Name the file `YEAR_Company.pdf` (e.g. `2025_Apple.pdf`) so the app parses the company and fiscal year from the filename.

Files live in `data/raw_pdfs/` (git-ignored — large, and best re-fetched than committed). `scripts/download_sample_reports.md` documents the sources.

> **Common Pitfall** — Fetching from SEC with a browser-like User-Agent gets you a polite "Undeclared Automated Tool" HTML page, not the filing. You must declare a real UA string with contact info. This exact trap cost real debugging time (see §19).

---

## 4. System Architecture

Three containers, one network, orchestrated by Docker Compose:

```
┌─────────────┐     HTTP      ┌──────────────┐   SQL/pgvector   ┌────────────┐
│  ui         │ ────────────▶ │  api         │ ───────────────▶ │  db        │
│  Streamlit  │  BACKEND_URL  │  FastAPI     │                  │  Postgres  │
│  :8501      │ ◀──────────── │  :8000       │ ◀─────────────── │  +pgvector │
└─────────────┘   JSON        └──────────────┘   rows            │  :5432     │
                                     │                            └────────────┘
                                     ├─▶ fastembed (local embeddings, in-process)
                                     └─▶ Google Gemini API (LLM: extract + chat)
```

- **ui** (Streamlit) is a thin client. It never touches the database or the LLM directly — it only calls the API over HTTP. This mirrors a real frontend/backend split.
- **api** (FastAPI) owns all logic: ingestion, embedding (in-process via fastembed), vector storage, retrieval, LLM calls, and persistence.
- **db** (Postgres with the `pgvector` extension) is *one* database holding **both** the vector store (`chunks` table) and the structured KPIs (`financial_metrics` table). No separate vector database to run.

> **Key Takeaway** — Consolidating vectors and structured data into a single Postgres is the biggest simplification versus the reference (which used a separate Azure AI Search service). One datastore, one thing to run, one thing to back up.

The `providers/` seam (config-driven) means "switch to Azure" is a configuration and add-a-module change, not a rewrite. See §15.

---

## 5. Concept Primer: Retrieval-Augmented Generation (RAG)

An LLM only knows what was in its training data (plus whatever you put in the prompt). RAG is the pattern of **retrieving** relevant text at query time and **augmenting** the prompt with it, so the model answers from *your* documents rather than its memory.

The lifecycle has two phases:

**Ingestion (offline, once per document):**
1. **Load** the document (PDF).
2. **Transform** it to clean text (Markdown, to preserve tables).
3. **Split** it into **chunks** small enough to embed and retrieve.
4. **Embed** each chunk into a vector (a list of numbers capturing meaning).
5. **Store** the vectors in a vector database.

**Query (online, per question):**
1. **Embed** the query with the same model.
2. **Retrieve** the nearest chunks by vector similarity.
3. **Augment** a prompt with those chunks.
4. **Generate** an answer with the LLM.

Our KPI extraction is RAG with a twist: instead of a user question, the "query" is a set of fixed retrieval queries per financial statement, and the "answer" is **structured JSON** rather than prose.

> **Interview angle** — Be able to draw the two-phase diagram from memory and name what each phase costs (ingestion is compute-heavy but one-time; query is latency-sensitive and repeated).

---

## 6. Concept Primer: Embeddings, Vector Search, and pgvector

An **embedding** is a fixed-length vector (here, 384 floats) produced by a model such that texts with similar meaning have vectors that are close together. "Cash from operations" and "operating cash flow" land near each other even though they share no words.

**Similarity** is measured by **cosine distance** — the angle between two vectors. Small angle = similar. In SQL with pgvector that is the `<=>` operator:

```sql
SELECT content FROM chunks
ORDER BY embedding <=> :query_vector
LIMIT 8;
```

To make that fast at scale, pgvector builds an **HNSW index** (Hierarchical Navigable Small World) — an approximate-nearest-neighbour graph that finds close vectors without scanning every row.

**pgvector** is a PostgreSQL extension that adds a `vector` column type and these operators. The table:

```sql
CREATE TABLE chunks (
  id BIGSERIAL PRIMARY KEY, company VARCHAR(100), year VARCHAR(10),
  source_file VARCHAR(255), content TEXT, embedding vector(384)
);
CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);
```

> **Common Pitfall** — The vector column dimension is fixed at table-creation time and **must** match your embedding model's output (bge-small = 384, gemini-embedding-001 = up to 3072). Change models and you must recreate the table. We hit exactly this when switching providers.

---

## 7. Folder Structure, File by File

```
investor-intelligence/
├── app.py                     FastAPI entry; lifespan runs DB init on startup
├── config.py                  all settings (env-driven); the free⇄Azure seam
├── ingestion/
│   ├── pdf_to_markdown.py      PDF → Markdown via pymupdf4llm (keeps tables)
│   ├── chunker.py              markdown-aware recursive splitter (no torch)
│   └── ingest_documents.py     orchestrator + idempotent + graceful extraction
├── embeddings/
│   └── provider.py             fastembed (local, default) / Gemini (API) behind one interface
├── llm/
│   └── gemini.py               structured-JSON extraction + chat, with 429 retry
├── vectorstore/
│   └── pgvector_store.py       store + hybrid retriever (vector + keyword)
├── rag/
│   └── kpi_extractor.py        retrieval queries + prompt + FinancialMetrics schema
├── database/
│   ├── db.py                   engine + schema init (pgvector, tables, indexes)
│   ├── save_metrics.py         insert KPI rows
│   └── metrics.py              read latest KPI row per company/year
├── routes/
│   ├── health.py  ingestion.py  chat.py  dashboard.py   FastAPI routers
├── frontend/
│   └── streamlit_app.py        Dashboard / Upload / AI Analyst tabs
├── k8s/                        phase-2 Kubernetes manifests (api + ui)
├── .github/workflows/ci.yml    lint + test + docker build
├── docker-compose.yml          db + api + ui
├── Dockerfile, frontend/Dockerfile
├── tests/test_smoke.py         config, chunker, app-wiring tests
├── README.md  HANDBOOK.md  scripts/download_sample_reports.md
└── data/raw_pdfs/  data/markdown/   (git-ignored artifacts)
```

The layout deliberately mirrors the reference project's package names (`ingestion/`, `vectorstore/`, `llm/`, `rag/`, `database/`, `routes/`) so anyone who watched the tutorial recognises it instantly — only the *implementations* differ.

---

## 8. Code Walkthrough — Configuration (`config.py`)

Everything that changes between "free local" and "Azure production" lives in one Pydantic `Settings` class, loaded from environment / `.env`.

**8.1 Why one config object.** Pydantic-settings validates types and gives a single import (`get_settings()`) used everywhere. The `@lru_cache` makes it a singleton.

```python
class Settings(BaseSettings):
    llm_provider: str = "gemini"
    gemini_model: str = "gemini-flash-lite-latest"
    embedding_provider: str = "local"     # fastembed by default
    local_embed_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384              # MUST match the model
    chunk_size: int = 2200
    embed_max_rpm: int = 90
```

**8.2 The derived DB URL.** `database_url` is a computed property so the Postgres host/port/creds come from separate env vars (which also feed the compose `db` service), keeping one source of truth.

> **Key Takeaway** — Provider choice, model names, dimensions, and rate limits are all data, not code. That is what makes the free⇄Azure swap a config change.

---

## 9. Code Walkthrough — Ingestion (`ingestion/`)

**9.1 `pdf_to_markdown.py`.** One function wraps `pymupdf4llm.to_markdown()`. Markdown is chosen over plain text specifically because it **preserves table structure** — critical for financial statements.

**9.2 `chunker.py` — a markdown-aware recursive splitter.** The reference uses LangChain's `SemanticChunker`, which embeds every sentence to find split points — expensive and rate-limited. We implement a lightweight recursive splitter that tries progressively finer separators (`\n## `, `\n\n`, `\n`, `. `, ` `) to keep chunks near `chunk_size` characters, then applies character overlap so context isn't cut mid-fact. No heavy dependencies.

**9.3 `ingest_documents.py` — the orchestrator.** This is where the two most important design ideas live:

```python
def ingest_document(pdf_path):
    company, year = parse_company_year(Path(pdf_path))
    md = convert_pdf(pdf_path, ...)
    chunks = chunk_markdown_file(md)
    store = PgVectorStore()
    store.delete_company(company, year)     # idempotent: no duplicate chunks
    stored = store.upload_chunks(chunks, company, year, pdf_file.name)
    try:
        metrics = extract_and_save(company, year_int, store=store)   # LLM
    except Exception as exc:
        metrics, metrics_error = None, str(exc)   # keep the chunks!
    return {..., "chunks_stored": stored, "metrics": metrics, "metrics_error": metrics_error}
```

- **Idempotency:** `delete_company` runs before insert, so re-uploading a file replaces its chunks instead of duplicating them.
- **Decoupling:** storage (local, always succeeds) is separated from LLM extraction (rate-limited). If the LLM call fails, the document is still stored and searchable; KPIs can be generated later.

> **Common Pitfall** — Without idempotency, every re-upload triples your chunk count (we saw 372 = 3×124 Apple chunks before adding `delete_company`). Retrieval still works but storage bloats and duplicates skew results.

---

## 10. Code Walkthrough — Embeddings and the pgvector Store

**10.1 `embeddings/provider.py`.** A tiny abstraction with two implementations behind `get_embeddings()`:

- `LocalEmbeddings` (default) — `fastembed.TextEmbedding("BAAI/bge-small-en-v1.5")`. ONNX-based, **no torch**, **no API quota**. `query_embed` / `passage_embed` apply the right bge prefixes.
- `GeminiEmbeddings` — the API path, with client-side **rate limiting** (`embed_max_rpm`) and **429 retry** honouring the server's `retry_delay`.

**10.2 `vectorstore/pgvector_store.py`.**
- `PgVectorStore.upload_chunks` embeds all chunk texts, then bulk-inserts rows with the vector cast (`CAST(:embedding AS vector)`), formatting each vector as pgvector's `[0.1,0.2,...]` literal.
- `Retriever.invoke` embeds the query and runs the cosine-distance `ORDER BY embedding <=> :qvec LIMIT k`, optionally filtered by company/year.
- `Retriever.keyword_search` (added later) is a **lexical** lookup: `content ILIKE '%Total assets%'`. This is the other half of hybrid retrieval — see §12 and §19.

> **Key Takeaway** — Local embeddings turned the highest-volume operation (hundreds of embed calls per filing) into a free, offline, quota-immune step. That single decision is what made ingesting real 100-page 10-Ks possible.

---

## 11. Code Walkthrough — The LLM Provider (`llm/gemini.py`)

Two public functions and a retry helper:

- `get_structured_completion(prompt, response_model)` — calls Gemini with `response_mime_type="application/json"`, then parses the response into a Pydantic model, with a regex fallback that pulls the first `{...}` out of the text if the model wraps it. Robustness matters because free models don't always return clean JSON.
- `generate_text(prompt)` — plain-text answer for the chat endpoint.
- `_generate_with_retry(...)` — wraps every call, catching `ResourceExhausted` (429) and sleeping the server-suggested `retry_delay` before retrying. This absorbs the free tier's tight per-minute limits.

```python
def _generate_with_retry(model, *args, retries=4, **kwargs):
    for attempt in range(retries):
        try:
            return model.generate_content(*args, **kwargs)
        except ResourceExhausted as exc:
            if attempt == retries - 1: raise
            seconds = getattr(getattr(exc, "retry_delay", None), "seconds", 0) or 0
            time.sleep(max(seconds + 1, 2 ** attempt))
```

> **Interview angle** — "How do you handle rate limits?" Answer with two layers: *proactive* client-side pacing (embeddings) and *reactive* retry-with-backoff honouring the server's `retry_delay` (LLM). And a third, architectural layer: decouple the rate-limited step so a 429 never destroys completed work.

---

## 12. Code Walkthrough — RAG KPI Extraction (`rag/kpi_extractor.py`)

This is the intellectual core.

**12.1 The schema.** `FinancialMetrics` is a Pydantic model with the eight KPI fields. Passing it to `get_structured_completion` gives typed, validated output.

**12.2 Hybrid retrieval.** `retrieve_context` runs **two kinds** of retrieval and merges unique chunks:

1. **Vector queries** — one focused query per financial statement (income statement, cash flow, balance sheet, risk factors, growth drivers). Focused queries retrieve better than one broad query.
2. **Lexical keyword search** — `keyword_search(["Total assets", "Total liabilities", "Net cash provided by operating activities", ...])`. This *guarantees* the number-heavy statement chunks are in context.

Why both? Embedding models rank **dense numeric tables poorly** against natural-language queries. In testing, the balance-sheet chunk containing "Total assets $ 450,256 $ 595,281" was *never* in the vector top-5 for Google or Microsoft, so those fields came back null. Adding the lexical half fixed it immediately.

**12.3 The two-year rule.** The prompt explicitly instructs the model to take the **most recent** fiscal year (usually the right-hand column) when statements show two years — with a worked example. That's why Google resolves to $595,281M (current), not $450,256M (prior).

> **Key Takeaway** — Pure vector search is not enough for financial documents. Hybrid (vector + lexical) retrieval is the production-correct pattern, and this project demonstrates *why* with a concrete failure and fix.

---

## 13. Code Walkthrough — The API (`app.py`, `routes/`)

`app.py` builds the FastAPI app; a `lifespan` handler runs `init_db()` on startup (creates the pgvector extension, tables, and indexes if missing). Four routers:

- `health` — `GET /health` liveness.
- `ingestion` — `POST /api/upload` (store + attempt extract, always 200 if storage succeeded) and `POST /api/extract` (re-run the single LLM extraction from stored chunks — the "Generate KPIs" retry path).
- `chat` — `POST /api/chat` (retrieve → prompt → `generate_text`).
- `dashboard` — `GET /api/metrics` (latest KPI row per company/year), `GET /api/ingested` (companies that have chunks but maybe not KPIs), `GET /api/companies`.

The upload route's message adapts to whether extraction succeeded or was rate-limited, so the UI can guide the user to click "Generate KPIs".

> **Common Pitfall** — Letting a rate-limited LLM call raise a 500 from `/api/upload` would throw away the (expensive, successful) embedding work. The route returns 200 with a `metrics_error` instead. Design your error boundaries around *what work you'd lose*.

---

## 14. Code Walkthrough — The Streamlit UI (`frontend/streamlit_app.py`)

Three tabs, all talking to the API over `BACKEND_URL`:

- **Dashboard** — a company selector, KPI metric cards, risk/growth expanders, and a "Compare companies" table. It also lists any documents that are *ingested but un-extracted* and offers a **Generate KPIs** button per company (calls `/api/extract`).
- **Upload** — file uploader → `POST /api/upload`, with a spinner and a success/warning message driven by the response.
- **AI Analyst** — company scope selector + question box → `POST /api/chat`.

`@st.cache_data(ttl=15)` caches metric fetches briefly; `fetch_metrics.clear()` busts the cache after an upload or extraction.

> **Interview angle** — "Why Streamlit and not React?" Honest answer: the reference's "React frontend" was actually a server-rendered Jinja2 page; Streamlit gives a real, separate UI service in pure Python with far less code, which suited a solo build. The frontend/backend split (HTTP only) is preserved.

---

## 15. Every Design Decision, Justified

Each decision states **what was given up**.

1. **Gemini instead of Azure OpenAI.** Free. Gave up: enterprise SLAs, and generous quotas — the free tier is tight (see §19).
2. **Local fastembed instead of API embeddings.** No quota, offline, fast enough. Gave up: the very best embedding quality (bge-small is small) and a slightly bigger image. Worth it — API embeddings literally could not ingest a 100-page filing on the free tier.
3. **pgvector instead of a dedicated vector DB.** One datastore for vectors + KPIs; simpler ops. Gave up: the scale ceiling and managed features of Azure AI Search / a specialised vector DB.
4. **Docker Compose instead of AKS (for local).** Zero cost, one command. Gave up: real orchestration, autoscaling, rolling deploys — provided as phase-2 `k8s/` manifests instead.
5. **Streamlit instead of React/Jinja2.** Less code, pure Python. Gave up: full control over frontend UX.
6. **Hybrid retrieval instead of pure vector.** Reliability on numeric tables. Gave up: a little simplicity — but the pure-vector version was *wrong* on balance sheets.
7. **Decoupled ingestion/extraction.** Resilience to LLM rate limits. Gave up: a single-shot "upload does everything" simplicity, in exchange for never losing embedding work.
8. **Markdown-aware chunker instead of SemanticChunker.** No per-sentence embedding cost. Gave up: semantically "perfect" boundaries — recursive splitting is good enough and far cheaper.
9. **Extract-once, serve-from-Postgres.** KPIs computed at ingest and served from a table (cheap reads); the vector store is queried live only for chat. Gave up: always-fresh recomputation, which you don't need for static filings.

> **Interview angle** — Interviewers love "what did you trade off?" Every item here is a ready answer that shows you understood the cost, not just the benefit.

---

## 16. Results and How to Read Them

Four authentic 10-Ks, all fields populated:

| Company | FY | Revenue | Net Income | Op. Income | Cash Flow | Total Assets | Total Liab. |
|---|---|---|---|---|---|---|---|
| Apple | 2025 | $416,161M | $112,010M | $133,050M | $111,482M | $359,241M | $285,508M |
| Google | 2025 | $402,836M | $132,170M | $129,039M | $164,713M | $595,281M | $180,016M |
| Microsoft | 2026 | $331,839M | $133,749M | $155,237M | $182,935M | $758,376M | $315,989M |
| Tesla | 2025 | $94,827M | $3,855M | $4,355M | $14,747M | $137,806M | $54,941M |

**How to read them honestly:** these are *extractions*, not audited figures — the value of the project is the pipeline, not the accounting. The correct evaluation question is "did the system retrieve the right chunk and read the right column?", and the answer, after the hybrid-retrieval fix, is yes for all four across all eight fields.

> **Common Pitfall** — Don't oversell extraction accuracy. Present it as "faithful extraction of stated figures", and be ready to discuss failure modes (a mis-scanned table, an unusual statement layout) and how you'd detect them (cross-checks like assets = liabilities + equity).

---

## 17. Testing Strategy

`tests/test_smoke.py` runs with no database and no API keys, so CI is fast and hermetic:

- `test_settings_database_url` — config builds a valid DSN.
- `test_chunker_splits_and_overlaps` — the chunker produces multiple, bounded, overlapping chunks.
- `test_health_route` — the FastAPI app builds and the health handler responds (without triggering the DB-initialising lifespan).

The philosophy: unit-test the **pure logic** (config, chunking) and the **wiring** (app imports, routes exist). The provider-dependent paths (embeddings, LLM, DB) are validated by running the real stack, because mocking them would test the mock, not the integration.

> **Interview angle** — "What would you add with more time?" Contract tests against a test Postgres (pgvector in CI via a service container), a golden-file test that asserts KPI extraction on a fixed small PDF, and retrieval-quality metrics (did the balance-sheet chunk make the context?).

---

## 18. Docker, CI, and Reproducibility

- **Two images.** `Dockerfile` (api, `uvicorn app:app`) and `frontend/Dockerfile` (ui, `streamlit run`). Both slim Python 3.12.
- **`docker-compose.yml`.** `db` (pgvector/pgvector:pg16 with a healthcheck), `api` (depends on db healthy, mounts `./data`), `ui` (depends on api). Secrets and model choices come from `.env` via compose interpolation.
- **CI (`.github/workflows/ci.yml`).** On push/PR: install deps, `ruff check`, `pytest`, then build both Docker images. Lint + test + build on every change.
- **Reproducibility.** Pinned `requirements.txt`; the DB schema is created idempotently on startup; sample data is documented and re-fetchable.

> **Key Takeaway** — Run it with three commands: set `GEMINI_API_KEY` in `.env`, `docker compose up --build`, open `:8501`.

---

## 19. Debugging Guide (Real Problems You Hit)

These are true war stories from the build — the most interview-valuable part of the document.

**19.1 "text-embedding-004 is not found."** The obvious embedding model name returned 404 for `embedContent` on this SDK/key. *Fix:* list models programmatically (`genai.list_models()` filtered by `embedContent`) and use what's actually available (`gemini-embedding-001`). **Lesson:** never assume model names; enumerate them.

**19.2 The model quota gauntlet.** `gemini-2.5-flash` → "not available to new users." `gemini-3.6-flash` → worked, but hit `GenerateRequestsPerDayPerProjectPerModel-FreeTier, limit: 20` — **20 requests per day**, exhausted by our own testing. *Fix:* switch to `gemini-flash-lite-latest`, which has a far higher free daily allowance. **Lesson:** free-tier LLM limits are *per model* and include brutal daily caps; read the `quota_id` in the error, don't just see "429".

**19.3 Embeddings couldn't ingest a real filing.** Gemini embeddings cap at ~100/minute plus a low daily cap; a 100-page 10-K is 100–350 chunks. Even with pacing and retry it exhausted the daily quota. *Fix:* move embeddings **local** (fastembed). **Lesson:** put your highest-volume operation where there is no quota.

**19.4 OOM on the big filings.** Ingesting Microsoft (143pp) and Tesla (159pp) killed the api container (`OOMKilled=true`) on colima's 3.8 GB. *Fix:* `colima start --cpu 4 --memory 8`. **Lesson:** ONNX embedding + Postgres + Streamlit together need headroom; know how to read `docker inspect ... OOMKilled`.

**19.5 The balance-sheet retrieval miss.** `total_assets`/`total_liabilities` were null for Google and Microsoft. The data *was* in a chunk (`Total assets $ 450,256 $ 595,281`) but pure vector search never ranked that dense numeric table in the top-5. *Fix:* **hybrid retrieval** (add lexical keyword search for exact statement labels) + a prompt rule for the two-year column. **Lesson:** embeddings under-rank number-heavy tables; combine with lexical search.

**19.6 The `.env` that broke compose.** A stray `= "AQ...` (space + unclosed quote) produced `unterminated quoted value` at "line 20" — because an unterminated quote is read to end-of-file. *Fix:* keep env values unquoted, no leading space. **Lesson:** compose's `.env` parser is strict; quote errors report the *wrong* line.

**19.7 The detached-stack trap.** Running `docker compose up` in the foreground means the whole stack dies when that terminal stops, and dependent containers then can't resolve `db`. *Fix:* run `docker compose up -d`. **Lesson:** for long-lived local stacks, detach.

> **Interview angle** — Pick two of these and tell them as stories: symptom → diagnosis → fix → lesson. §19.5 (hybrid retrieval) and §19.3 (local embeddings) are the strongest.

---

## 20. Production Readiness and Future Work

**What's production-shaped already:** clean module boundaries, a provider seam, idempotent ingestion, health checks, CI, containerisation, and resilience to LLM rate limits.

**What a real production deploy needs (the phase-2 path):**
- **Azure (or any cloud) providers** behind the existing seams: Azure OpenAI (`llm/`), Azure AI Search or managed pgvector (`vectorstore/`), Azure Database for PostgreSQL.
- **Kubernetes** — the `k8s/` manifests (api ClusterIP + ui LoadBalancer) and a GitHub Actions deploy job build/push to a registry and `kubectl apply`.
- **Secrets management** — Kubernetes Secrets / a vault, not `.env`.
- **Observability** — request logging, retrieval-quality metrics, LLM cost/latency dashboards.
- **Extraction QA** — cross-checks (assets ≈ liabilities + equity), confidence flags, human-in-the-loop review for low-confidence fields.
- **Auth & multi-tenant** — users, per-user document scoping.

> **Key Takeaway** — The architecture was built so that "go to Azure/K8s" is additive, not a rewrite. That's the whole point of the provider seam.

---

## 21. Interview Question Bank (50+ Q&A)

### Beginner

**Q1. What is RAG and why use it here?**
Retrieval-Augmented Generation: retrieve relevant document chunks and put them in the prompt so the LLM answers from your data. Used here because 10-Ks are too big for the context window, and we need grounded, traceable answers rather than the model's guesses.

**Q2. What is an embedding?**
A fixed-length vector representing meaning; similar texts have nearby vectors. We use 384-dim bge-small embeddings.

**Q3. Why convert PDF to Markdown, not plain text?**
Markdown preserves table structure. Financial statements are tables; plain text turns them into an unlabelled number soup.

**Q4. What does pgvector give you?**
A `vector` column type and similarity operators (`<=>` cosine) in Postgres, plus an HNSW index for fast approximate nearest-neighbour search — so vectors live in the same DB as the structured data.

**Q5. Why store KPIs in a table if you already have the vectors?**
Extract-once, serve-from-Postgres: the dashboard reads cheap structured rows; the vector store is only queried live for chat. It saves repeated LLM calls.

### Intermediate — RAG / ML

**Q6. Your vector search missed balance-sheet numbers. Why, and how did you fix it?**
Embedding models rank dense numeric tables poorly against natural-language queries, so the "Total assets" chunk wasn't in the top-k. Fixed with hybrid retrieval: add a lexical keyword search for exact statement labels, guaranteeing those chunks reach the LLM.

**Q7. How do you chunk, and why that way?**
A markdown-aware recursive splitter targeting ~2200 chars with overlap, splitting on headings then paragraphs then lines. Chosen over LangChain's SemanticChunker to avoid embedding every sentence (cost/quota).

**Q8. How do you get structured output from the LLM?**
Gemini's JSON mode (`response_mime_type="application/json"`) plus a Pydantic schema, with a regex fallback that extracts the first JSON object if the model adds prose.

**Q9. How do you handle the two-year columns in statements?**
An explicit prompt rule to take the most-recent fiscal year (usually the right-hand column) with a worked example, reinforced by retrieving the right chunk.

**Q10. How would you evaluate retrieval quality?**
Did the required chunk (e.g. the balance sheet) appear in the assembled context? Track recall@k per KPI on a labelled set; alert if a statement chunk is missing.

### Intermediate — Engineering

**Q11. Why decouple storage from extraction?**
Storage uses local embeddings (no quota, always succeeds); extraction calls a rate-limited LLM. Decoupling means a 429 never discards the expensive embedding work — the doc stays searchable and KPIs are retried cheaply.

**Q12. How is ingestion idempotent?**
`delete_company(company, year)` runs before inserting, so re-uploading replaces chunks instead of duplicating them.

**Q13. How do you handle rate limits?**
Proactive client-side pacing for embeddings (RPM cap), reactive retry-with-backoff honouring the server's `retry_delay` for the LLM, and architectural decoupling so failures don't cascade.

**Q14. Why one Postgres for vectors and KPIs?**
Fewer moving parts: one datastore to run, back up, and secure. pgvector makes it possible.

**Q15. Walk me through a request from upload to dashboard.**
Upload → save PDF → Markdown → chunk → local embed → pgvector insert → hybrid retrieve → Gemini structured JSON → `financial_metrics` row → dashboard reads the row.

### Advanced

**Q16. Where does this break at scale, and what changes?**
Single-node Postgres and in-process embedding are the ceilings. At scale: a managed vector DB or partitioned pgvector, a dedicated embedding service, async ingestion via a queue, and horizontal api replicas on Kubernetes.

**Q17. How would you productionise extraction accuracy?**
Cross-field validation (assets ≈ liabilities + equity), per-field confidence, retrieval-recall monitoring, and human review for low-confidence extractions.

**Q18. How is the design portable to Azure?**
Providers sit behind seams (`llm/`, `embeddings/`, `vectorstore/`) selected by config; adding Azure implementations plus wiring the `k8s/` manifests to ACR/AKS reproduces the reference deployment without touching app logic.

**Q19. Security concerns?**
Secrets out of `.env` into a vault; SQL built with bound parameters (no string interpolation of user data); the API key never logged; SEC/robots-respectful fetching.

**Q20. Why not fine-tune a model on 10-Ks?**
Cost, staleness (new filings constantly), and loss of traceability. RAG grounds answers in the actual document and updates instantly when you ingest a new one.

*(Add your own as you rehearse — aim to answer any of §15's trade-offs as a question.)*

---

## 22. Resume Talking Points

**30 seconds:**
> "I built a production-style RAG application that reads company 10-Ks and extracts financial KPIs into a comparison dashboard with an AI chatbot. It's an open-stack rebuild of an Azure tutorial — I swapped in Gemini, local embeddings, and pgvector so it runs free, which forced real engineering around rate limits and retrieval quality."

**2 minutes:** add the pipeline (PDF→Markdown→chunk→embed→pgvector→retrieve→LLM→JSON→Postgres), and the two signature fixes: moving embeddings local to beat the free-tier quota, and hybrid (vector + lexical) retrieval to reliably pull number-heavy balance-sheet tables that pure vector search under-ranked.

**5 minutes:** walk the architecture diagram, the provider seam (free⇄Azure), the decoupled/idempotent ingestion, and two war stories from §19 (the quota gauntlet and the balance-sheet retrieval miss), ending on results (four real 10-Ks, zero blank fields) and the phase-2 Kubernetes path.

---

## 23. Glossary

- **10-K** — a company's annual report filed with the SEC; the source document.
- **Chunk** — a small slice of a document, embedded and stored for retrieval.
- **Cosine distance** — similarity measure between vectors (`<=>` in pgvector).
- **EDGAR** — the SEC's public filing database.
- **Embedding** — a vector representing a text's meaning.
- **fastembed** — an ONNX-based local embedding library (no torch, no API).
- **Hybrid retrieval** — combining vector (semantic) and lexical (keyword) search.
- **HNSW** — the approximate-nearest-neighbour index pgvector uses.
- **Idempotent** — re-running produces the same state (no duplicate chunks here).
- **KPI** — key performance indicator; here, the financial figures extracted.
- **pgvector** — a Postgres extension adding vector storage and search.
- **RAG** — Retrieval-Augmented Generation.
- **RPM / RPD** — requests per minute / per day (quota units).
- **XBRL** — the structured-data format SEC filings are tagged in (their HTML is "inline XBRL").

---

## 24. Final Revision Notes

**10 facts to have cold:**
1. It's a RAG app: PDF → Markdown → chunk → embed → pgvector → retrieve → Gemini → JSON → Postgres → dashboard.
2. Open-stack rebuild of an Azure tutorial; providers swapped, architecture preserved.
3. Embeddings are **local** (fastembed, bge-small, 384-dim) — no quota; that's what made ingesting real 10-Ks possible.
4. LLM is Gemini `gemini-flash-lite-latest` (chosen for its higher free daily quota).
5. One Postgres holds **both** vectors (pgvector `chunks`) and KPIs (`financial_metrics`).
6. Retrieval is **hybrid**: focused vector queries + lexical keyword search for statement labels.
7. Ingestion is **idempotent** (delete-before-insert) and **decoupled** from extraction (resilient to 429s).
8. Markdown preserves tables; plain text would destroy the financial statements.
9. Extract-once, serve-from-Postgres for cheap dashboard reads.
10. Phase-2 to Azure/K8s is additive because providers sit behind config-driven seams.

**3 sentences that win interviews:**
- "Pure vector search under-ranks number-heavy financial tables, so I added hybrid retrieval with a lexical fallback for exact statement labels — that's what made balance-sheet extraction reliable."
- "I moved the highest-volume operation, embeddings, off the API and onto a local model so free-tier quotas couldn't block ingestion of a 100-page filing."
- "I decoupled storage from LLM extraction so a rate-limit error never discards completed embedding work — the document stays searchable and KPIs are retried in one cheap call."

**Concept one-liners:** RAG = retrieve then generate. Embedding = meaning as a vector. pgvector = vectors in Postgres. Hybrid retrieval = semantic + keyword. Idempotent ingest = safe re-uploads.

**The red-flag question, pre-answered:** *"Are these numbers accurate?"* — "They're faithful extractions of the figures stated in the filing, not audited output; the project's value is the pipeline and its retrieval correctness, and I validate that the right chunk and the right year-column were read."

**If you freeze, say this:** "Let me walk the data from the PDF to the dashboard," and narrate the pipeline — it structures the whole answer.

*You didn't just follow a tutorial — you rebuilt it on a harder, free stack, hit real production walls (quotas, OOM, retrieval failures), and engineered your way through each one. That story is worth more than the code.*
