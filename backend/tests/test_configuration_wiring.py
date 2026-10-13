"""Exercise configuration consumers without downloading models or calling an LLM."""

import importlib.util
import sys
from types import ModuleType

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from app.settings import BACKEND_DIR, Settings


def load_module(relative_path, name):
    spec = importlib.util.spec_from_file_location(name, BACKEND_DIR / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_embedding_model_is_configured_lazy_and_cached(monkeypatch):
    settings = Settings.from_env({"EMBEDDING_MODEL": "test-model"}, env_file=None)
    monkeypatch.setattr("app.settings.get_settings", lambda: settings)
    created = []
    transformer = ModuleType("sentence_transformers")

    class FakeModel:
        def __init__(self, model_name):
            created.append(model_name)
            self.max_seq_length = 128
            self.tokenizer = FakeTokenizer()

        def get_sentence_embedding_dimension(self):
            return 3

        def encode(self, texts):
            class Vectors:
                def tolist(self):
                    return [[1.0, 0.0, 0.0] for _ in texts]
            return Vectors()

    class FakeTokenizer:
        model_max_length = 512

        def __call__(self, text, **kwargs):
            return {"input_ids": [0] * (len(text.split()) + 2)}

    transformer.SentenceTransformer = FakeModel
    monkeypatch.setitem(sys.modules, "sentence_transformers", transformer)
    module = load_module("app/services/embeddings.py", "test_embeddings_config")
    assert created == []
    assert module.embedding_dimension() == 3
    assert module.tokenizer_and_limit()[1] == 128
    assert module.embed_texts(["example"]) == [[1.0, 0.0, 0.0]]
    with pytest.raises(ValueError, match="silent truncation"):
        module.embed_texts(["word " * 127])
    module._get_model().tokenizer.model_max_length = 64
    assert module.tokenizer_and_limit()[1] == 64
    assert created == ["test-model"]


def test_qdrant_uses_configured_collection_and_model_dimension(monkeypatch):
    settings = Settings.from_env({"QDRANT_URL": "http://configured:6333", "QDRANT_COLLECTION": "custom"}, env_file=None)
    monkeypatch.setattr("app.settings.get_settings", lambda: settings)
    embeddings = ModuleType("app.services.embeddings")
    embeddings.embedding_dimension = lambda: 3
    monkeypatch.setitem(sys.modules, "app.services.embeddings", embeddings)
    local_client = QdrantClient(location=":memory:")
    urls = []

    def client_factory(*, url):
        urls.append(url)
        return local_client

    monkeypatch.setattr("qdrant_client.QdrantClient", client_factory)
    module = load_module("app/services/vector_store.py", "test_vector_config")
    try:
        module.ensure_collection()
        module.ensure_collection()
        assert urls == ["http://configured:6333"]
        assert local_client.get_collection("custom").config.params.vectors.size == 3
        local_client.delete_collection("custom")
        local_client.create_collection("custom", vectors_config=VectorParams(size=4, distance=Distance.COSINE))
        with pytest.raises(ValueError, match="incompatible"):
            module.ensure_collection()
    finally:
        local_client.close()


def test_groq_reads_dotenv_key_and_configured_model(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GROQ_API_KEY=test-secret\nLLM_MODEL=test-llm\n")
    settings = Settings.from_env({}, env_file=env_file)
    monkeypatch.setattr("app.settings.get_settings", lambda: settings)
    groq = ModuleType("langchain_groq")
    created = []
    groq.ChatGroq = lambda **kwargs: created.append(kwargs) or object()
    monkeypatch.setitem(sys.modules, "langchain_groq", groq)
    module = load_module("app/rag/generation.py", "test_groq_config")
    assert created == []
    assert module._get_llm() is module._get_llm()
    assert created == [{"model": "test-llm", "api_key": "test-secret", "temperature": 0}]


def test_missing_groq_key_fails_only_when_generation_is_requested(monkeypatch):
    settings = Settings.from_env({}, env_file=None)
    monkeypatch.setattr("app.settings.get_settings", lambda: settings)
    groq = ModuleType("langchain_groq")
    groq.ChatGroq = lambda **kwargs: pytest.fail("must not initialize without a key")
    monkeypatch.setitem(sys.modules, "langchain_groq", groq)
    module = load_module("app/rag/generation.py", "test_missing_key")
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        module._get_llm()


def test_api_respects_configured_cors_and_upload_limit(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient

    settings = Settings.from_env({"MAX_UPLOAD_MB": "1", "CORS_ORIGINS": "https://ui.example.com", "DATA_DIR": str(tmp_path)}, env_file=None)
    monkeypatch.setattr("app.settings.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.document_store.get_settings", lambda: settings)

    def unexpected_call(*args, **kwargs):
        pytest.fail("Rejected uploads must not reach ingestion or generation")

    for name, functions in {
        "app.services.chunking": ["chunk_document"],
        "app.services.embeddings": ["embed_texts"],
        "app.services.extraction": ["extract_pdf"],
        "app.services.vector_store": ["ensure_collection", "upsert_chunks"],
        "app.rag.retriever": ["retrieve_chunks"],
        "app.rag.generation": ["generate_answer"],
    }.items():
        stub = ModuleType(name)
        for function in functions:
            setattr(stub, function, unexpected_call)
        if name.endswith("extraction"):
            stub.ExtractionError = type("ExtractionError", (Exception,), {})
        if name.endswith("chunking"):
            stub.CHUNKING_VERSION = "section-token-offsets-v2"
            stub.CHUNK_OVERLAP_TOKENS = 32
        monkeypatch.setitem(sys.modules, name, stub)

    api = ModuleType("app.api")
    identity = load_module("app/services/ingestion_identity.py", "test_identity_config")
    monkeypatch.setitem(sys.modules, "app.services.ingestion_identity", identity)
    api.papers = load_module("app/api/papers.py", "test_papers_config")
    monkeypatch.setitem(sys.modules, "app.api.papers", api.papers)
    api.chat = load_module("app/api/chat.py", "test_chat_config")
    monkeypatch.setitem(sys.modules, "app.api", api)
    main = load_module("app/main.py", "test_main_config")

    with TestClient(main.app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        allowed = client.options("/chat", headers={
            "Origin": "https://ui.example.com", "Access-Control-Request-Method": "POST",
        })
        assert allowed.status_code == 200
        assert allowed.headers["access-control-allow-origin"] == "https://ui.example.com"
        denied = client.options("/chat", headers={
            "Origin": "https://other.example.com", "Access-Control-Request-Method": "POST",
        })
        assert denied.status_code == 400
        assert "access-control-allow-origin" not in denied.headers
        oversized = client.post("/papers/upload", files={
            "file": ("paper.pdf", b"x" * (1024 * 1024 + 1), "application/pdf"),
        })
        assert oversized.status_code == 413
        assert oversized.json() == {"detail": "File exceeds 1MB limit"}


def test_generation_preserves_missing_and_multiple_pages(monkeypatch):
    from types import SimpleNamespace

    groq = ModuleType("langchain_groq")
    groq.ChatGroq = lambda **kwargs: pytest.fail("No live LLM should be initialized")
    monkeypatch.setitem(sys.modules, "langchain_groq", groq)
    module = load_module("app/rag/generation.py", "test_page_citations")
    prompts = []

    def invoke(prompt):
        prompts.append(prompt)
        return SimpleNamespace(content="Answer")

    monkeypatch.setattr(module, "_get_llm", lambda: SimpleNamespace(invoke=invoke))
    chunks = [
        {"text": "Unknown page evidence", "section": "Intro", "page": None,
         "pages": [], "provenance_complete": False},
        {"text": "Multiple page evidence", "section": "Methods", "page": 2,
         "pages": [2, 4], "provenance_complete": True},
    ]
    result = module.generate_answer("Question", chunks + [chunks[1]])
    from app.models.schemas import ChatResponse

    response = ChatResponse(**result)
    assert len(response.citations) == 2
    assert response.citations[0].page is None
    assert response.citations[0].pages == []
    assert response.citations[0].provenance_complete is False
    assert response.citations[1].pages == [2, 4]
    assert response.citations[1].page_start == 2 and response.citations[1].page_end == 4
    assert "Pages: unknown" in prompts[0]
