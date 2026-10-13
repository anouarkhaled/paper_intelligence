"""Validated backend configuration; importing this module starts no services."""

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

from dotenv import dotenv_values

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _http_url(value: str, name: str, *, origin: bool = False) -> str:
    try:
        parts = urlsplit(value)
        parts.port  # Validate malformed and out-of-range ports.
    except ValueError:
        raise ValueError(f"{name} must be a valid HTTP(S) URL") from None
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
        or any(char.isspace() for char in value)
        or (origin and parts.path not in {"", "/"})
    ):
        raise ValueError(f"{name} must be a valid HTTP(S) {'origin' if origin else 'URL'}")
    return value.rstrip("/")


@dataclass(frozen=True)
class Settings:
    qdrant_url: str
    qdrant_collection: str
    embedding_model: str
    llm_model: str
    data_dir: Path
    max_upload_mb: int
    cors_origins: tuple[str, ...]
    groq_api_key: str | None = field(repr=False)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        env_file: Path | None = BACKEND_DIR / ".env",
    ) -> "Settings":
        # Disable interpolation so configuration is not affected by unrelated
        # process variables. Explicit process values always beat .env values.
        values = dict(dotenv_values(env_file, interpolate=False)) if env_file else {}
        values.update(os.environ if environ is None else environ)

        def read(name: str, default: str) -> str:
            value = values.get(name, default)
            if value is None or not value.strip():
                raise ValueError(f"{name} must not be empty")
            return value.strip()

        raw_limit = read("MAX_UPLOAD_MB", "50")
        try:
            max_upload_mb = int(raw_limit)
        except ValueError:
            raise ValueError("MAX_UPLOAD_MB must be a positive integer") from None
        if max_upload_mb <= 0:
            raise ValueError("MAX_UPLOAD_MB must be a positive integer")

        data_dir = Path(read("DATA_DIR", "data"))
        if not data_dir.is_absolute():
            data_dir = BACKEND_DIR / data_dir

        origins = read("CORS_ORIGINS", "http://localhost:5173").split(",")
        cors_origins = tuple(_http_url(o.strip(), "CORS_ORIGINS", origin=True) for o in origins)
        api_key = values.get("GROQ_API_KEY")
        return cls(
            qdrant_url=_http_url(read("QDRANT_URL", "http://localhost:6333"), "QDRANT_URL"),
            qdrant_collection=read("QDRANT_COLLECTION", "papers"),
            embedding_model=read("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            llm_model=read("LLM_MODEL", "llama-3.3-70b-versatile"),
            data_dir=data_dir.resolve(),
            max_upload_mb=max_upload_mb,
            cors_origins=cors_origins,
            groq_api_key=api_key.strip() if api_key and api_key.strip() else None,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Read configuration once per process. Restart after changing variables."""
    return Settings.from_env()
