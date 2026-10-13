"""Durable document metadata. This module neither indexes vectors nor authorizes users."""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Literal

from app.settings import get_settings

MIGRATIONS_DIR = Path(__file__).with_name("migrations")
MIGRATIONS = ("001_documents.sql",)


@dataclass(frozen=True)
class Document:
    document_id: str
    owner_id: str
    filename: str
    source_checksum: str
    pipeline_version: str
    status: Literal["processing", "ready", "failed"]
    num_pages: int | None
    num_chunks: int | None
    failure_code: str | None
    created_at: str
    updated_at: str


class DocumentNotFoundError(LookupError):
    """Document is absent or belongs to a different owner."""


class InvalidTransitionError(ValueError):
    """Only processing documents may become ready or failed."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class DocumentStore:
    def __init__(self, database_path: Path):
        self.database_path = Path(database_path)
        if str(self.database_path) == ":memory:":
            raise ValueError("DocumentStore requires a persistent database file")

    @classmethod
    def from_settings(cls) -> "DocumentStore":
        # Construction does not create files. Call initialize() explicitly.
        return cls(get_settings().data_dir / "documents.sqlite3")

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        """Apply pending schema migrations atomically; safe to call repeatedly."""
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            # Serialize migration checks across processes. Do not use
            # executescript(): it can commit an existing transaction implicitly.
            connection.execute("BEGIN IMMEDIATE")
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            if version > len(MIGRATIONS):
                raise RuntimeError("Database schema is newer than this application")
            for index in range(version, len(MIGRATIONS)):
                sql = (MIGRATIONS_DIR / MIGRATIONS[index]).read_text()
                connection.execute(sql)
                connection.execute(f"PRAGMA user_version = {index + 1}")

    def create(
        self, *, document_id: str, owner_id: str, filename: str,
        source_checksum: str, pipeline_version: str,
    ) -> Document:
        """Register processing metadata; SQLite rejects duplicates/invalid values."""
        timestamp = _now()
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO documents
                (document_id, owner_id, filename, source_checksum, pipeline_version,
                 status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'processing', ?, ?)""",
                (document_id, owner_id, filename, source_checksum, pipeline_version,
                 timestamp, timestamp),
            )
            return self._get(connection, document_id, owner_id)

    @staticmethod
    def _get(connection: sqlite3.Connection, document_id: str, owner_id: str) -> Document:
        row = connection.execute(
            "SELECT * FROM documents WHERE document_id = ? AND owner_id = ?",
            (document_id, owner_id),
        ).fetchone()
        if row is None:
            raise DocumentNotFoundError("Document not found for this owner")
        return Document(**dict(row))

    def get(self, document_id: str, *, owner_id: str) -> Document:
        with self._connection() as connection:
            return self._get(connection, document_id, owner_id)

    def list_documents(self, *, owner_id: str) -> list[Document]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM documents WHERE owner_id = ? ORDER BY created_at, document_id",
                (owner_id,),
            ).fetchall()
            return [Document(**dict(row)) for row in rows]

    def find_ingestion(
        self, *, owner_id: str, source_checksum: str, pipeline_version: str,
    ) -> Document | None:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT * FROM documents
                WHERE owner_id = ? AND source_checksum = ? AND pipeline_version = ?""",
                (owner_id, source_checksum, pipeline_version),
            ).fetchone()
            return Document(**dict(row)) if row else None

    def mark_ready(
        self, document_id: str, *, owner_id: str, num_pages: int, num_chunks: int,
    ) -> Document:
        return self._transition(
            document_id, owner_id, "ready", num_pages, num_chunks, None,
        )

    def mark_failed(self, document_id: str, *, owner_id: str, failure_code: str) -> Document:
        """Store a safe error code (e.g. extraction_failed), never raw exceptions."""
        return self._transition(document_id, owner_id, "failed", None, None, failure_code)

    def _transition(
        self, document_id: str, owner_id: str, status: str,
        num_pages: int | None, num_chunks: int | None, failure_code: str | None,
    ) -> Document:
        with self._connection() as connection:
            changed = connection.execute(
                """UPDATE documents SET status = ?, num_pages = ?, num_chunks = ?,
                failure_code = ?, updated_at = ?
                WHERE document_id = ? AND owner_id = ? AND status = 'processing'""",
                (status, num_pages, num_chunks, failure_code, _now(), document_id, owner_id),
            ).rowcount
            document = self._get(connection, document_id, owner_id)
            if changed == 0:
                raise InvalidTransitionError("Document is no longer processing")
            return document
