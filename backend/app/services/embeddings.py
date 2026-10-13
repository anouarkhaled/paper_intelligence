from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.models.errors import EmbeddingInputTooLongError
from app.settings import get_settings


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(get_settings().embedding_model)


def embedding_dimension() -> int:
    dimension = _get_model().get_sentence_embedding_dimension()
    if dimension is None:
        raise ValueError("The configured embedding model must have a fixed output dimension")
    return dimension


def tokenizer_and_limit():
    """Read the loaded model's effective limit, not only the tokenizer default."""
    model = _get_model()
    tokenizer = model.tokenizer
    limit = model.max_seq_length
    tokenizer_limit = tokenizer.model_max_length
    if isinstance(tokenizer_limit, int) and 0 < tokenizer_limit < 1_000_000:
        limit = min(limit, tokenizer_limit)
    if not isinstance(limit, int) or limit <= 0:
        raise ValueError("The embedding model must declare a positive token limit")
    return tokenizer, limit


def embed_texts(texts: list[str]) -> list[list[float]]:
    tokenizer, limit = tokenizer_and_limit()
    if any(len(tokenizer(text, add_special_tokens=True, truncation=False)["input_ids"]) > limit for text in texts):
        raise EmbeddingInputTooLongError("Embedding input exceeds the model token limit; refusing silent truncation")
    vectors = _get_model().encode(texts)
    return vectors.tolist()
