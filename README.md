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

```
GROQ_API_KEY=your_key_here
```

Run the API:

```bash
uvicorn app.main:app --reload
```

Serves on `http://127.0.0.1:8000`. Interactive docs at `/docs`.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Serves on `http://localhost:5173`.

### Tests

```bash
cd backend
pytest -v
```

## Roadmap

- [x] Milestone 1 — Project setup
- [x] Milestone 2 — Document extraction
- [x] Milestone 3 — Embeddings + vector DB
- [x] Milestone 4 — RAG chatbot
- [x] Milestone 5 — Frontend integration
- [ ] Evaluation dataset & quality metrics (Phase 10)
- [ ] Advanced features — summaries, comparison, LangGraph (Phase 11)
