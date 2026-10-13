# SQLite document metadata

Upload and chat use this store instead of a process-local dictionary. FastAPI's
lifespan initializes the database and migrations before accepting requests.

## Storage responsibilities

- SQLite records document identity, ownership, ingestion status and counts.
- Qdrant stores vectors and searchable chunk payloads.
- Source PDFs remain temporary; their bytes are not retained after ingestion.
- Authentication and automated ingestion recovery are not implemented yet.

`DocumentStore.from_settings()` selects `DATA_DIR/documents.sqlite3` without
creating files. Call `initialize()` explicitly before using the store. It creates
the directory and applies numbered SQL migrations using SQLite's `user_version`.
Each migration file contains one SQL statement. All pending migrations run in
one transaction; a failed migration rolls back its schema and version updates.
A database newer than the application is rejected, not downgraded.

## Lifecycle

Create a document in `processing`, then call either:

- `mark_ready(..., num_pages=..., num_chunks=...)` after successful indexing.
- `mark_failed(..., failure_code="extraction_failed")` after failure.

Only processing documents can transition. Ready/failed documents are terminal
in this version; retry/recovery behavior belongs to the ingestion issue. Counts
must be positive integers when ready and absent otherwise. Failure codes must
be nonempty. Supply safe codes rather than exception messages or secrets.

The unique `(owner_id, source_checksum, pipeline_version)` constraint prevents
duplicate ingestion identities while permitting another owner or pipeline
version to ingest the same source. Checksums must be lowercase SHA-256 hex.
The upload route computes SHA-256 from the uploaded bytes. A pipeline fingerprint
includes the current token-based ingestion algorithm, overlap target, embedding
model and Qdrant target. Dependencies and model revisions are not pinned yet,
so this fingerprint is not a complete reproducibility manifest.

All reads and transitions require an owner ID. The API currently supplies the
fixed server-side owner `local`: this is single-user development, not access
control between HTTP clients. Future authentication must supply the principal;
never trust an arbitrary client-supplied owner.

## API integration

- Upload inserts `processing` before extraction. It marks `ready` only after
  Qdrant confirms completed indexing; extraction/indexing failures are recorded
  as safe failure codes and produce controlled HTTP errors.
- Uploading identical bytes to the same pipeline returns the original ready
  document ID and metadata (including its original filename), without indexing
  again. A processing/failed duplicate returns 409; retry is a future issue.
- Chat reads SQLite and accepts only ready records for the current pipeline.
  Missing documents return 404; processing/failed or incompatible records return
  409. SQLite failures return 503.
- Heavy ingestion runs in a thread pool, with one ingestion allowed per process
  because the cached Docling converter's concurrency safety is unverified.
  Concurrent ingestion receives 429. Run one API worker for this development setup.
- Restarting the API preserves paper IDs if both SQLite and Qdrant data persist.
  There is no migration of old in-memory metadata; previously uploaded papers
  must be uploaded again. The frontend still holds its document state in memory.

## Transactions and errors

Each operation opens and closes its own connection. SQL values use parameters.
Failed writes roll back; guarded updates prevent a terminal state from being
overwritten. Migration initialization uses `BEGIN IMMEDIATE` to serialize
concurrent initialization. Ordinary writes wait up to five seconds for a lock.

- `sqlite3.IntegrityError`: invalid metadata, duplicate identity, or invalid counts.
- `DocumentNotFoundError`: missing document or a different owner.
- `InvalidTransitionError`: the document is no longer processing.

Timestamps are UTC ISO-8601 strings. Creation time is preserved on transitions.
SQLite and Qdrant do not share a transaction. A crash can leave a processing
record or orphaned/partially written vectors. Such records cannot be chatted
with, but reconciliation, cleanup and automatic retry remain future work.

The database is local state and must not be committed. Use a persistent volume
for deployment. This design targets a small single-instance application;
multiple replicas/shared storage will require revisiting the database choice.

## Verification

From `backend/`, with the existing pytest dependency installed:

```bash
python -m pytest -q tests/test_document_store.py tests/test_persistent_api.py
```

Tests use temporary file-backed databases and check reopening, owner filtering,
uniqueness, SQL parameterization, state transitions, write rollback and atomic
migrations. API integration tests additionally exercise real file-backed Qdrant
storage, reopen both stores, and check failure responses. They require FastAPI,
httpx, python-multipart and qdrant-client. Extraction, embeddings and generation
use test doubles; no model downloads, Qdrant server or API key are needed.
