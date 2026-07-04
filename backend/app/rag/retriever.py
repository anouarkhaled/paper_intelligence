from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.services.embeddings import embed_texts
from app.services.vector_store import COLLECTION_NAME, client

TOP_K = 5


def retrieve_chunks(paper_id: str, question: str, top_k: int = TOP_K) -> list[dict]:
    query_vector = embed_texts([question])[0]

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=Filter(
            must=[FieldCondition(key="paper_id", match=MatchValue(value=paper_id))]
        ),
        limit=top_k,
    ).points

    return [point.payload for point in results]
