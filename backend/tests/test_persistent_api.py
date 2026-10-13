"""Real SQLite and Qdrant local storage, with extraction/models replaced by doubles."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient
from qdrant_client.models import UpdateStatus

from app.dependencies import LOCAL_OWNER_ID
from app.settings import BACKEND_DIR, Settings


def load(relative_path, name):
    spec = importlib.util.spec_from_file_location(name, BACKEND_DIR / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    settings = Settings.from_env({"DATA_DIR": str(tmp_path / "metadata")}, env_file=None)
    monkeypatch.setattr("app.settings.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.document_store.get_settings", lambda: settings)
    state = {"failure": None, "extractions": 0, "generations": 0, "paths": []}
    extraction = ModuleType("app.services.extraction")
    extraction.ExtractionError = type("ExtractionError", (Exception,), {})

    def extract(path):
        state["extractions"] += 1
        state["paths"].append(Path(path))
        assert Path(path).read_bytes()
        if state["failure"] == "extraction":
            raise extraction.ExtractionError("private error detail")
        return SimpleNamespace(pages={1: object(), 2: object()})

    extraction.extract_pdf = extract
    chunking = ModuleType("app.services.chunking")
    chunking.CHUNK_SIZE_WORDS = 500
    chunking.CHUNK_OVERLAP_WORDS = 50
    chunking.chunk_document = lambda doc: [] if state["failure"] == "empty" else [
        {"text": "Transformer evidence", "section": "Introduction", "page": 1},
    ]
    embeddings = ModuleType("app.services.embeddings")
    embeddings.embedding_dimension = lambda: 3

    def embed(texts):
        if state["failure"] == "embedding":
            raise RuntimeError("private embedding error")
        if state["failure"] == "count":
            return []
        return [[1.0, 0.0, 0.0] for _ in texts]

    embeddings.embed_texts = embed
    generation = ModuleType("app.rag.generation")

    def answer(question, chunks):
        state["generations"] += 1
        assert chunks and chunks[0]["text"] == "Transformer evidence"
        return {"answer": "A Transformer", "citations": [{"section": "Introduction", "page": 1}]}

    generation.generate_answer = answer
    for module in [extraction, chunking, embeddings, generation]:
        monkeypatch.setitem(sys.modules, module.__name__, module)
    # A file-backed Qdrant client also survives application/store reconstruction.
    vector_client = QdrantClient(path=str(tmp_path / "vectors"))
    monkeypatch.setattr("qdrant_client.QdrantClient", lambda **kwargs: vector_client)
    vectors = load("app/services/vector_store.py", "persistent_vectors")
    upsert = vectors.upsert_chunks

    def controlled_upsert(*args):
        if state["failure"] == "index":
            raise RuntimeError("private index error")
        return upsert(*args)

    vectors.upsert_chunks = controlled_upsert
    monkeypatch.setitem(sys.modules, "app.services.vector_store", vectors)
    retriever = load("app/rag/retriever.py", "persistent_retriever")
    monkeypatch.setitem(sys.modules, "app.rag.retriever", retriever)
    api = ModuleType("app.api")
    identity = load("app/services/ingestion_identity.py", "persistent_identity")
    monkeypatch.setitem(sys.modules, "app.services.ingestion_identity", identity)
    api.papers = load("app/api/papers.py", "persistent_papers")
    api.chat = load("app/api/chat.py", "persistent_chat")
    monkeypatch.setitem(sys.modules, "app.api", api)

    def new_app():
        return load("app/main.py", "persistent_main").app

    def reopen_vectors():
        nonlocal vector_client
        vector_client.close()
        vector_client = QdrantClient(path=str(tmp_path / "vectors"))
        vectors.client = vector_client
        retriever.client = vector_client

    try:
        yield SimpleNamespace(new_app=new_app, reopen_vectors=reopen_vectors, state=state,
                              vectors=vectors, settings=settings, identity=identity, papers=api.papers)
    finally:
        vector_client.close()


def upload(client, contents=b"%PDF-test", filename="paper.pdf"):
    return client.post("/papers/upload", files={"file": (filename, contents, "application/pdf")})


def test_upload_then_chat_after_application_restart(runtime):
    app = runtime.new_app()
    with TestClient(app) as client:
        response = upload(client)
        assert response.status_code == 200
        body = response.json()
        assert body["num_pages"] == 2 and body["num_chunks"] == 1
        assert app.state.document_store.get(body["paper_id"], owner_id=LOCAL_OWNER_ID).status == "ready"
    runtime.reopen_vectors()
    restarted = runtime.new_app()
    with TestClient(restarted) as client:
        assert restarted.state.document_store is not app.state.document_store
        response = client.post("/chat", json={"paper_id": body["paper_id"], "question": "What architecture?"})
        assert response.status_code == 200
        assert response.json()["answer"] == "A Transformer"
        duplicate = upload(client, filename="renamed.pdf")
        assert duplicate.json() == body
    assert runtime.state["extractions"] == 1
    assert all(not path.exists() for path in runtime.state["paths"])


@pytest.mark.parametrize("failure,code,status", [
    ("extraction", "extraction_failed", 422),
    ("empty", "extraction_failed", 422),
    ("embedding", "ingestion_failed", 503),
    ("count", "ingestion_failed", 503),
    ("index", "ingestion_failed", 503),
])
def test_failed_ingestion_is_persistent_and_not_queryable(runtime, failure, code, status):
    runtime.state["failure"] = failure
    app = runtime.new_app()
    with TestClient(app) as client:
        response = upload(client)
        assert response.status_code == status
        assert "private" not in response.text
        document, = app.state.document_store.list_documents(owner_id=LOCAL_OWNER_ID)
        assert document.status == "failed" and document.failure_code == code
        response = client.post("/chat", json={"paper_id": document.document_id, "question": "Explain"})
        assert response.status_code == 409
        assert upload(client).status_code == 409
    assert runtime.state["generations"] == 0
    assert all(not path.exists() for path in runtime.state["paths"])


def test_processing_unknown_and_other_owner_are_not_queryable(runtime):
    app = runtime.new_app()
    with TestClient(app) as client:
        store = app.state.document_store
        store.create(document_id="processing", owner_id=LOCAL_OWNER_ID, filename="p.pdf",
                     source_checksum="a" * 64, pipeline_version="v1")
        store.create(document_id="other-owner", owner_id="other", filename="p.pdf",
                     source_checksum="b" * 64, pipeline_version="v1")
        store.mark_ready("other-owner", owner_id="other", num_pages=1, num_chunks=1)
        for paper_id, status in [("processing", 409), ("unknown", 404), ("other-owner", 404)]:
            response = client.post("/chat", json={"paper_id": paper_id, "question": "Explain"})
            assert response.status_code == status
    assert runtime.state["generations"] == 0


def test_rejected_inputs_create_no_metadata(runtime):
    app = runtime.new_app()
    with TestClient(app) as client:
        assert client.post("/papers/upload", files={"file": ("x.txt", b"text", "text/plain")}).status_code == 400
        assert client.post("/papers/upload", files={"file": ("x.pdf", b"", "application/pdf")}).status_code == 422
        assert app.state.document_store.list_documents(owner_id=LOCAL_OWNER_ID) == []
    assert runtime.state["extractions"] == 0


def test_indexing_must_be_confirmed_before_document_is_ready(runtime, monkeypatch):
    monkeypatch.setattr(runtime.vectors.client, "upsert", lambda **kwargs: SimpleNamespace(status=UpdateStatus.ACKNOWLEDGED))
    app = runtime.new_app()
    with TestClient(app) as client:
        assert upload(client).status_code == 503
        document, = app.state.document_store.list_documents(owner_id=LOCAL_OWNER_ID)
        assert document.status == "failed"


def test_blank_question_and_changed_pipeline_do_not_generate(runtime, monkeypatch):
    app = runtime.new_app()
    with TestClient(app) as client:
        paper_id = upload(client).json()["paper_id"]
        assert client.post("/chat", json={"paper_id": paper_id, "question": " "}).status_code == 400
    from dataclasses import replace

    changed = replace(runtime.settings, qdrant_collection="another-index")
    monkeypatch.setattr(runtime.identity, "get_settings", lambda: changed)
    with TestClient(runtime.new_app()) as client:
        assert client.post("/chat", json={"paper_id": paper_id, "question": "Explain"}).status_code == 409
    assert runtime.state["generations"] == 0


def test_busy_ingestion_is_rejected_without_creating_metadata(runtime):
    with TestClient(runtime.new_app()) as client:
        with runtime.papers.INGESTION_LOCK:
            assert upload(client).status_code == 429
        assert upload(client).status_code == 200
    assert runtime.state["extractions"] == 1


def test_database_errors_have_controlled_responses(runtime):
    import sqlite3

    app = runtime.new_app()
    with TestClient(app) as client:
        with sqlite3.connect(app.state.document_store.database_path) as connection:
            connection.execute("DROP TABLE documents")
        assert upload(client).status_code == 503
        response = client.post("/chat", json={"paper_id": "missing", "question": "Explain"})
        assert response.status_code == 503
        assert response.json() == {"detail": "Document metadata store is unavailable"}
