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

- Frontend: React, Tailwind
- Backend: FastAPI
- AI: LangChain
- PDF extraction: Docling
- Vector DB: Qdrant
- Embeddings: Sentence Transformers

## Setup

_TBD once backend environment is initialized (Phase 5)._

## Roadmap

- [ ] Milestone 1 — Project setup
- [ ] Milestone 2 — Document extraction
- [ ] Milestone 3 — Embeddings + vector DB
- [ ] Milestone 4 — RAG chatbot
- [ ] Milestone 5 — Frontend integration
