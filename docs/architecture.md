# Architecture — Research Paper Assistant

## Tech Stack (frozen for MVP)

| Layer       | Choice               |
|-------------|----------------------|
| Frontend    | React + Tailwind     |
| Backend     | FastAPI              |
| AI orchestration | LangChain       |
| PDF extraction | Docling            |
| Vector DB   | Qdrant               |
| Embeddings  | Sentence Transformers |

## High-Level Flow

```
React UI
   |
FastAPI API
   |
Document Processing Pipeline
   |
Docling  ->  Chunking  ->  Embeddings  ->  Vector DB
   |
Retriever
   |
LLM
```

## Component Notes

For each component below: why it exists, its inputs, its outputs.
Fill this in as each piece gets built — treat it as a living doc, not a
one-time diagram.

### React UI
- **Why:** user-facing upload + chat interface
- **Input:** user actions (upload PDF, ask question)
- **Output:** calls to FastAPI endpoints, renders responses

### FastAPI API
- **Why:** single entry point, request validation, orchestration
- **Input:** HTTP requests from frontend
- **Output:** JSON responses (paper_id, chat answers, etc.)

### Docling (extraction)
- **Why:** turns raw PDF bytes into structured text (sections, pages)
- **Input:** PDF file
- **Output:** structured document (JSON-like) with section/page metadata

### Chunking
- **Why:** breaks structured document into retrieval-sized units without
  losing section/page context
- **Input:** structured document from Docling
- **Output:** list of chunks, each with `{text, section, page}` metadata

### Embeddings
- **Why:** turns chunk text into vectors for semantic search
- **Input:** chunk text
- **Output:** vector per chunk

### Qdrant (vector DB)
- **Why:** stores chunk vectors + metadata, supports similarity search
- **Input:** (vector, metadata) pairs at ingestion; query vector at retrieval
- **Output:** top-k similar chunks with metadata

### Retriever
- **Why:** given a question, finds the most relevant chunks
- **Input:** user question (embedded)
- **Output:** top-k relevant chunks (with section/page for citation)

### LLM
- **Why:** generates a natural-language answer grounded in retrieved chunks
- **Input:** question + retrieved chunks (prompt)
- **Output:** answer text + citation references
