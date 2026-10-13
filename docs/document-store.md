# SQLite document metadata

The metadata store is implemented independently of the API. Upload and chat
still use their existing in-memory registry until the next integration issue.

## Storage responsibilities

- SQLite records document identity, ownership, ingestion status and counts.
- Qdrant stores vectors and searchable chunk payloads.
- This step does not retain PDFs, index vectors, or implement authentication.

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
The store validates their format but does not compute or verify PDF checksums.

All reads and transitions require an owner ID. The eventual API must derive it
from a trusted server-side identity, never trust an arbitrary client-supplied
owner. These filters prepare for access control; they do not provide auth yet.

## Transactions and errors

Each operation opens and closes its own connection. SQL values use parameters.
Failed writes roll back; guarded updates prevent a terminal state from being
overwritten. Migration initialization uses `BEGIN IMMEDIATE` to serialize
concurrent initialization. Ordinary writes wait up to five seconds for a lock.

- `sqlite3.IntegrityError`: invalid metadata, duplicate identity, or invalid counts.
- `DocumentNotFoundError`: missing document or a different owner.
- `InvalidTransitionError`: the document is no longer processing.

Timestamps are UTC ISO-8601 strings. Creation time is preserved on transitions.
SQLite and Qdrant do not share a transaction; this store alone cannot guarantee
vector/metadata consistency. The ingestion upgrade must mark ready only after
confirmed indexing and handle interrupted writes explicitly.

The database is local state and must not be committed. Use a persistent volume
for deployment. This design targets a small single-instance application;
multiple replicas/shared storage will require revisiting the database choice.

## Verification

From `backend/`, with the existing pytest dependency installed:

```bash
python -m pytest -q tests/test_document_store.py
```

Tests use temporary file-backed databases and check reopening, owner filtering,
uniqueness, SQL parameterization, state transitions, write rollback and atomic
migrations. No models, Qdrant service or API key are needed.
