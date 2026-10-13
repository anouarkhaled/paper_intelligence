import hashlib
import json

from app.services.chunking import CHUNK_OVERLAP_WORDS, CHUNK_SIZE_WORDS
from app.settings import get_settings


def pipeline_version() -> str:
    settings = get_settings()
    # Include the target index so changing collection/model does not reuse an
    # upload whose vectors live elsewhere. Full artifact versioning comes later.
    manifest = {
        "ingestion": "born-digital-sections-v1",
        "chunk_words": CHUNK_SIZE_WORDS,
        "overlap_words": CHUNK_OVERLAP_WORDS,
        "embedding_model": settings.embedding_model,
        "qdrant_url": settings.qdrant_url,
        "qdrant_collection": settings.qdrant_collection,
    }
    return hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
