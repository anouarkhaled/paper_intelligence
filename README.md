# Research Paper Assistant

## Project Overview

An AI-powered application that lets users upload scientific papers and
interact with them through natural language — summarization, question
answering, comparison, and literature analysis.

See [docs/requirements.md](docs/requirements.md) for full scope and
requirements, and [docs/architecture.md](docs/architecture.md) for the
system design.

## Architecture

```
React UI -> FastAPI API -> Document Processing Pipeline
              (Docling -> Chunking -> Embeddings -> Qdrant)
                         -> Retriever -> LLM
```

## Tech Stack

- Frontend: React, Tailwind (Vite)
- Backend: FastAPI
- AI: LangChain, Groq (LLM inference)
- PDF extraction: Docling
- Vector DB: Qdrant
- Embeddings: Sentence Transformers (`all-MiniLM-L6-v2`)

## Setup

### Prerequisites

- Python 3.11+ (see `backend/venv` setup below)
- Node.js 20+
- Docker (for Qdrant)
- A [Groq API key](https://console.groq.com) (free tier available)

### 1. Vector database (Qdrant)

```bash
docker run -d --name qdrant -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
```

### 2. Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

Create `backend/.env`:

```bash
cp .env.example .env
```

Set `GROQ_API_KEY` in that file before asking questions. Never commit the key.
On Windows, use `Copy-Item .env.example .env`.

Run the API:

```bash
uvicorn app.main:app --reload
```

Serves on `http://127.0.0.1:8000`. Interactive docs at `/docs`.

### 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Serves on `http://localhost:5173`.

### Configuration

`backend/app/settings.py` reads `backend/.env` regardless of the working
directory. Exported environment variables override that file. Values are
validated and cached once per process; restart the backend after changes.
Relative `DATA_DIR` paths resolve from `backend/`. Reading configuration does
not create directories, download models, or contact services.

| Backend variable | Default | Purpose |
|---|---|---|
| `QDRANT_URL` | `http://localhost:6333` | HTTP(S) vector database endpoint |
| `QDRANT_COLLECTION` | `papers` | Collection used for ingestion and retrieval |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence Transformers model |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Groq model identifier |
| `DATA_DIR` | `data` | SQLite metadata location (`documents.sqlite3`) when the store is initialized |
| `MAX_UPLOAD_MB` | `50` | Positive integer upload limit, in MiB |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated HTTP(S) origins; no wildcard |
| `GROQ_API_KEY` | None | Required when generating answers; excluded from settings repr |

The frontend reads `VITE_API_URL` from its own `.env`, defaulting to
`http://127.0.0.1:8000`. Vite embeds this public value at startup/build time;
restart or rebuild after changing it. Never put credentials in `VITE_*` variables.

The embedding model loads on first use and determines the collection's vector
dimension. Changing models requires a new `QDRANT_COLLECTION` and re-ingestion,
even if the models have the same dimension: their embedding spaces differ.
Collection dimension/distance mismatches fail rather than silently reusing an
incompatible index. Dependency versions and model revisions are not pinned yet.

### Current scope and limitations

Implemented routes: `GET /health`, `POST /papers/upload`, and `POST /chat`.
Summary generation is planned, not implemented. Paper metadata is still in
memory and is lost on restart. The SQLite metadata store and migrations are
implemented but not yet connected to these routes; setting `DATA_DIR` alone
does not persist API uploads. See [document-store design](docs/document-store.md).
Only born-digital PDFs are supported; OCR is disabled. Upload size is currently
checked after reading the file. Citations list retrieved sections/pages and are
not yet validated against individual answer claims. See `docs/milestones.md`
for historical tasks; unchecked boxes there do not establish current runtime
status. The upgrade will reconcile that historical checklist separately.

### Tests

```bash
cd backend
pytest -v
```

Configuration checks do not require Docling, model downloads, a Qdrant server,
or a Groq key. In a Python environment with `pytest`, `python-dotenv`, and
`qdrant-client`, `fastapi`, `python-multipart`, and `httpx` installed:

```bash
cd backend
python -m pytest -q tests/test_settings.py tests/test_configuration_wiring.py
```

The standalone metadata store can be tested without model or service dependencies:

```bash
python -m pytest -q tests/test_document_store.py
```

The Qdrant configuration test uses an in-memory client; model and LLM
construction are replaced with test doubles. A FastAPI test checks the configured
CORS allowlist and upload limit without invoking ingestion. The full suite still
exercises Docling against the committed PDF fixture.

## Roadmap

- [x] Milestone 1 — Project setup
- [x] Milestone 2 — Document extraction
- [x] Milestone 3 — Embeddings + vector DB
- [x] Milestone 4 — RAG chatbot
- [x] Milestone 5 — Frontend integration
- [ ] Evaluation dataset & quality metrics (Phase 10)
- [ ] Advanced features — summaries, comparison, LangGraph (Phase 11)
