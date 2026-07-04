import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

client = QdrantClient(url="http://localhost:6333")

COLLECTION_NAME = "papers"
VECTOR_SIZE = 384  # all-MiniLM-L6-v2 output dim, verified in LEARNING_LOG.md


def ensure_collection() -> None:
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
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
