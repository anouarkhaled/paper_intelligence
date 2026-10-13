import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.services.embeddings import embedding_dimension
from app.settings import get_settings

settings = get_settings()
client = QdrantClient(url=settings.qdrant_url)

COLLECTION_NAME = settings.qdrant_collection


def ensure_collection() -> None:
    vector_size = embedding_dimension()
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
    else:
        vectors = client.get_collection(COLLECTION_NAME).config.params.vectors
        if (
            not isinstance(vectors, VectorParams)
            or vectors.size != vector_size
            or vectors.distance != Distance.COSINE
        ):
            raise ValueError(
                "Qdrant collection is incompatible with the configured embedding model. "
                "Choose a new QDRANT_COLLECTION and re-ingest documents."
            )


def upsert_chunks(paper_id: str, chunks: list[dict], vectors: list[list[float]]) -> None:
    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={**chunk, "paper_id": paper_id},
        )
        for chunk, vector in zip(chunks, vectors)
    ]
    client.upsert(collection_name=COLLECTION_NAME, points=points)
