# API Contract (MVP)

Defined before implementation (Step 13) so frontend and backend can be
built against a shared, stable interface. Changing this later is fine, but
changes should be deliberate, not accidental drift.

## `GET /health`

Basic liveness check — no logic, just confirms the server is up and
responding. Useful for local dev and later for deployment health checks.

**Response 200:**
```json
{ "status": "ok" }
```

## `POST /papers/upload`

Uploads a PDF, triggers the extraction/chunking/embedding pipeline
(Docling -> chunk -> embed -> store in Qdrant), and returns an ID to
reference this paper in later requests.

Metadata is persisted in SQLite. Repeating an identical upload with the same
pipeline/index configuration returns the original ready ID and filename.
The API uses a fixed server-side owner for single-user development; no auth yet.

**Request:** `multipart/form-data` with a single `file` field (the PDF).

**Response 200:**
```json
{
  "paper_id": "b3f1c2e0-...-uuid",
  "filename": "attention_is_all_you_need.pdf",
  "num_pages": 15,
  "num_chunks": 84
}
```

**Error cases (define behavior now, not while debugging later):**
| Case | Status | Body |
|---|---|---|
| Not a PDF | 400 | `{ "detail": "File must be a PDF" }` |
| File > configured `MAX_UPLOAD_MB` (default 50) | 413 | `{ "detail": "File exceeds 50MB limit" }` (message reflects configured limit) |
| Docling fails to parse (e.g. scanned/image-only PDF) | 422 | `{ "detail": "Could not extract text from PDF" }` |
| Empty file | 422 | `{ "detail": "PDF file is empty" }` |
| Duplicate processing/failed ingestion | 409 | Current state and unsupported automatic retry |
| Another ingestion is active in this process | 429 | `{ "detail": "Another document is being processed; try again later" }` |
| Embedding/indexing failure | 503 | `{ "detail": "Document ingestion failed" }` |
| SQLite operation fails | 503 | `{ "detail": "Document metadata store is unavailable" }` |

## `POST /chat`

Ask a question about a previously uploaded paper. Runs retrieval + LLM
generation, returns an answer grounded in cited chunks (NFR2).

**Request:**
```json
{
  "paper_id": "b3f1c2e0-...-uuid",
  "question": "What is the main contribution of this paper?"
}
```

**Response 200:**
```json
{
  "answer": "The main contribution is a new architecture called the Transformer...",
  "citations": [
    { "section": "Introduction", "page": 1 },
    { "section": "3.2 Model Architecture", "page": 3 }
  ]
}
```

**Error cases:**
Citation objects retain `section` and nullable `page` (first known source page).
They additionally return `pages` (exact known pages), nullable `page_start` /
`page_end`, and `provenance_complete`. An empty `pages` list with null bounds
means unknown provenance. Bounds do not imply that all intermediate pages are
known; use `pages`. Attribution is conservative at Docling text-item granularity,
not proof that the generated answer used those pages. Old word-based ingestions
must be re-uploaded after the v2 pipeline change.

| Case | Status | Body |
|---|---|---|
| `paper_id` not found | 404 | `{ "detail": "Paper not found" }` |
| Empty question | 400 | `{ "detail": "Question cannot be empty" }` |
| Question exceeds embedding token budget | 422 | `{ "detail": "Question exceeds the embedding model token limit" }` |
| Document processing/failed | 409 | `{ "detail": "Paper is not ready (processing)" }` (reflects current status) |
| Document belongs to another pipeline configuration | 409 | Re-upload required |
| SQLite operation fails | 503 | `{ "detail": "Document metadata store is unavailable" }` |

## `POST /papers/{paper_id}/summary`

**Planned endpoint — not implemented in the current application.**

Generates a structured summary of the paper (TLDR, key contributions,
limitations) — supports FR5. Separate endpoint from `/chat` because a
summary isn't a retrieval-driven Q&A, it's closer to "process the whole
document."

**Response 200:**
```json
{
  "tldr": "...",
  "key_contributions": ["...", "..."],
  "limitations": ["...", "..."]
}
```

---

## Design decisions worth noting

- **Why a `paper_id` instead of re-uploading the PDF on every chat
  request:** upload is expensive (parse + chunk + embed once), chat should
  be cheap and fast (NFR1: <5s). Separating them means the expensive work
  happens once, not per question.
- **Why citations are `{section, page}` objects, not just page numbers:**
  matches the chunk metadata decided in `docs/architecture.md` — the
  citation format is only as good as the metadata you attach at chunking
  time. This is why chunking strategy (Phase 7) has to be decided before
  this contract can actually be *implemented*, even though the contract
  itself can be written now.
- **MVP simplification:** single paper per `paper_id`, no session/user
  concept. Matches the "no auth, no multi-user" MVP boundary in
  `docs/requirements.md`.
