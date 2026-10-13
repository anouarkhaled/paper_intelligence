import hashlib
import json

from app.services.chunking import CHUNKING_VERSION, CHUNK_OVERLAP_TOKENS
from app.settings import get_settings


def pipeline_version() -> str:
    settings = get_settings()
    # Include the target index so changing collection/model does not reuse an
    # upload whose vectors live elsewhere. Full artifact versioning comes later.
    manifest = {
        "ingestion": CHUNKING_VERSION,
        "overlap_tokens": CHUNK_OVERLAP_TOKENS,
        "embedding_model": settings.embedding_model,
        "qdrant_url": settings.qdrant_url,
        "qdrant_collection": settings.qdrant_collection,
    }
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
