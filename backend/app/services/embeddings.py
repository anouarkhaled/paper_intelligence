from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.settings import get_settings


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(get_settings().embedding_model)


def embedding_dimension() -> int:
    dimension = _get_model().get_sentence_embedding_dimension()
    if dimension is None:
        raise ValueError("The configured embedding model must have a fixed output dimension")
    return dimension


def embed_texts(texts: list[str]) -> list[list[float]]:
    vectors = _get_model().encode(texts)
    return vectors.tolist()
