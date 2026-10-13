import pytest

from app.settings import BACKEND_DIR, Settings, get_settings


def test_development_defaults():
    settings = Settings.from_env({}, env_file=None)
    assert settings.qdrant_url == "http://localhost:6333"
    assert settings.qdrant_collection == "papers"
    assert settings.embedding_model == "all-MiniLM-L6-v2"
    assert settings.llm_model == "llama-3.3-70b-versatile"
    assert settings.data_dir == BACKEND_DIR / "data"
    assert settings.max_upload_bytes == 50 * 1024 * 1024
    assert settings.cors_origins == ("http://localhost:5173",)
    assert settings.groq_api_key is None


def test_environment_overrides_dotenv_without_mutating_process(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("QDRANT_COLLECTION=from-file\nLLM_MODEL=file-model\nGROQ_API_KEY=test-secret\n")
    monkeypatch.delenv("QDRANT_COLLECTION", raising=False)
    settings = Settings.from_env({"QDRANT_COLLECTION": "from-process"}, env_file=env_file)
    assert settings.qdrant_collection == "from-process"
    assert settings.llm_model == "file-model"
    assert settings.groq_api_key == "test-secret"
    import os

    assert "QDRANT_COLLECTION" not in os.environ
    assert "test-secret" not in repr(settings)


def test_all_environment_overrides(tmp_path):
    settings = Settings.from_env({
        "QDRANT_URL": "https://qdrant.example.com:6333/",
        "QDRANT_COLLECTION": "custom",
        "EMBEDDING_MODEL": "custom-embedding",
        "LLM_MODEL": "custom-llm",
        "DATA_DIR": str(tmp_path),
        "MAX_UPLOAD_MB": "10",
        "CORS_ORIGINS": " https://app.example.com/, http://localhost:5173 ",
    }, env_file=None)
    assert settings.qdrant_url == "https://qdrant.example.com:6333"
    assert settings.qdrant_collection == "custom"
    assert settings.embedding_model == "custom-embedding"
    assert settings.llm_model == "custom-llm"
    assert settings.data_dir == tmp_path
    assert settings.max_upload_bytes == 10 * 1024 * 1024
    assert settings.cors_origins == ("https://app.example.com", "http://localhost:5173")


def test_relative_data_path_does_not_depend_on_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = Settings.from_env({"DATA_DIR": "storage/papers"}, env_file=None)
    assert settings.data_dir == BACKEND_DIR / "storage/papers"


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "large", "", " "])
def test_invalid_upload_limit(value):
    with pytest.raises(ValueError, match="MAX_UPLOAD_MB"):
        Settings.from_env({"MAX_UPLOAD_MB": value}, env_file=None)


@pytest.mark.parametrize("value", [
    "ftp://example.com", "localhost:6333", "https://", "http://host:99999",
    "http://user:password@host", "http://host?token=sensitive", "http://bad host",
])
def test_invalid_qdrant_url_does_not_expose_value(value):
    with pytest.raises(ValueError, match="QDRANT_URL") as error:
        Settings.from_env({"QDRANT_URL": value}, env_file=None)
    assert value not in str(error.value)


@pytest.mark.parametrize("value", ["*", "http://host/path", "http://host,", "http://host#fragment"])
def test_invalid_cors_origin(value):
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        Settings.from_env({"CORS_ORIGINS": value}, env_file=None)


@pytest.mark.parametrize("name", ["QDRANT_COLLECTION", "EMBEDDING_MODEL", "LLM_MODEL", "DATA_DIR"])
def test_empty_required_setting(name):
    with pytest.raises(ValueError, match=name):
        Settings.from_env({name: " "}, env_file=None)


def test_settings_read_once_per_process(monkeypatch):
    get_settings.cache_clear()
    expected = Settings.from_env({}, env_file=None)
    calls = []

    def load(cls):
        calls.append(True)
        return expected

    monkeypatch.setattr(Settings, "from_env", classmethod(load))
    try:
        assert get_settings() is expected
        assert get_settings() is expected
        assert len(calls) == 1
    finally:
        get_settings.cache_clear()
