import sqlite3
from datetime import datetime

import pytest

from app.services.document_store import DocumentStore, DocumentNotFoundError, InvalidTransitionError
from app.settings import Settings


@pytest.fixture
def store(tmp_path):
    result = DocumentStore(tmp_path / "data" / "documents.sqlite3")
    result.initialize()
    return result


def create(store, **overrides):
    values = dict(document_id="paper-1", owner_id="alice", filename="paper.pdf",
                  source_checksum="a" * 64, pipeline_version="v1")
    values.update(overrides)
    return store.create(**values)


def test_constructor_uses_data_dir_without_creating_files(tmp_path, monkeypatch):
    settings = Settings.from_env({"DATA_DIR": str(tmp_path / "storage")}, env_file=None)
    monkeypatch.setattr("app.services.document_store.get_settings", lambda: settings)
    result = DocumentStore.from_settings()
    assert result.database_path == tmp_path / "storage" / "documents.sqlite3"
    assert not result.database_path.parent.exists()


def test_migration_is_repeatable_and_preserves_data(store):
    expected = create(store)
    store.initialize()
    store.initialize()
    assert store.get("paper-1", owner_id="alice") == expected
    with sqlite3.connect(store.database_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1


def test_ready_document_survives_reopening(store):
    original = create(store)
    ready = store.mark_ready("paper-1", owner_id="alice", num_pages=8, num_chunks=20)
    reopened = DocumentStore(store.database_path)
    assert reopened.get("paper-1", owner_id="alice") == ready
    assert ready.status == "ready"
    assert ready.created_at == original.created_at
    assert datetime.fromisoformat(ready.updated_at) >= datetime.fromisoformat(ready.created_at)
    assert datetime.fromisoformat(ready.created_at).utcoffset().total_seconds() == 0


def test_owner_scoped_reads_and_updates(store):
    create(store)
    assert store.list_documents(owner_id="bob") == []
    for operation in [
        lambda: store.get("paper-1", owner_id="bob"),
        lambda: store.mark_ready("paper-1", owner_id="bob", num_pages=1, num_chunks=1),
        lambda: store.mark_failed("paper-1", owner_id="bob", failure_code="extraction_failed"),
    ]:
        with pytest.raises(DocumentNotFoundError):
            operation()
    assert store.get("paper-1", owner_id="alice").status == "processing"


def test_duplicate_identity_is_owner_and_pipeline_scoped(store):
    create(store)
    with pytest.raises(sqlite3.IntegrityError):
        create(store, document_id="duplicate")
    create(store, document_id="bob-paper", owner_id="bob")
    create(store, document_id="new-pipeline", pipeline_version="v2")
    assert len(store.list_documents(owner_id="alice")) == 2


@pytest.mark.parametrize("overrides", [
    {"document_id": ""}, {"owner_id": " "}, {"filename": ""},
    {"pipeline_version": ""}, {"source_checksum": "bad"},
    {"source_checksum": "g" * 64},
])
def test_invalid_metadata_is_rejected(store, overrides):
    with pytest.raises(sqlite3.IntegrityError):
        create(store, **overrides)
    assert store.list_documents(owner_id="alice") == []


@pytest.mark.parametrize("pages,chunks", [(0, 1), (1, -1), (1.5, 2), (None, 1)])
def test_invalid_ready_counts_roll_back(store, pages, chunks):
    expected = create(store)
    with pytest.raises(sqlite3.IntegrityError):
        store.mark_ready("paper-1", owner_id="alice", num_pages=pages, num_chunks=chunks)
    assert store.get("paper-1", owner_id="alice") == expected


def test_failed_state_and_terminal_transition_guard(store):
    create(store)
    failed = store.mark_failed("paper-1", owner_id="alice", failure_code="extraction_failed")
    assert failed.status == "failed"
    assert failed.failure_code == "extraction_failed"
    assert failed.num_pages is None and failed.num_chunks is None
    with pytest.raises(InvalidTransitionError):
        store.mark_ready("paper-1", owner_id="alice", num_pages=1, num_chunks=1)
    assert store.get("paper-1", owner_id="alice") == failed


def test_ready_state_cannot_be_overwritten(store):
    create(store)
    ready = store.mark_ready("paper-1", owner_id="alice", num_pages=1, num_chunks=1)
    with pytest.raises(InvalidTransitionError):
        store.mark_failed("paper-1", owner_id="alice", failure_code="late_failure")
    assert store.get("paper-1", owner_id="alice") == ready


def test_empty_failure_code_rolls_back(store):
    expected = create(store)
    with pytest.raises(sqlite3.IntegrityError):
        store.mark_failed("paper-1", owner_id="alice", failure_code=" ")
    assert store.get("paper-1", owner_id="alice") == expected


def test_unknown_document(store):
    with pytest.raises(DocumentNotFoundError):
        store.get("missing", owner_id="alice")


def test_filename_is_stored_as_data_not_sql(store):
    filename = "paper'); DROP TABLE documents; --.pdf"
    create(store, filename=filename)
    assert store.get("paper-1", owner_id="alice").filename == filename


def test_future_schema_is_not_downgraded(store):
    with sqlite3.connect(store.database_path) as connection:
        connection.execute("PRAGMA user_version = 99")
    with pytest.raises(RuntimeError, match="newer"):
        store.initialize()
    with sqlite3.connect(store.database_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 99


def test_invalid_migration_rolls_back_schema_and_version(tmp_path, monkeypatch):
    import app.services.document_store as module

    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "first.sql").write_text("CREATE TABLE example (id INTEGER)")
    (migrations / "bad.sql").write_text("INVALID SQL")
    monkeypatch.setattr(module, "MIGRATIONS_DIR", migrations)
    monkeypatch.setattr(module, "MIGRATIONS", ("first.sql", "bad.sql"))
    result = DocumentStore(tmp_path / "documents.sqlite3")
    with pytest.raises(sqlite3.OperationalError):
        result.initialize()
    with sqlite3.connect(result.database_path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
        assert connection.execute("SELECT name FROM sqlite_master WHERE name = 'example'").fetchone() is None
