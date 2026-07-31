from sentence_transformers import SentenceTransformer

from research_platform import config

_model: SentenceTransformer | None = None


class EmbeddingModelError(Exception):
    pass


class EmbeddingModelLoadError(EmbeddingModelError):
    """Raised when the pinned model fails to load (bad revision, no network
    on first download, corrupted cache, etc). Wraps the original exception
    rather than swallowing it."""


def _load_model() -> SentenceTransformer:
    global _model
    if _model is not None:
        return _model
    try:
        _model = SentenceTransformer(
            config.EMBEDDING_MODEL_NAME,
            revision=config.EMBEDDING_MODEL_REVISION,
            device=config.EMBEDDING_DEVICE,
        )
    except Exception as exc:
        raise EmbeddingModelLoadError(
            f"failed to load embedding model {config.EMBEDDING_MODEL_NAME}"
            f"@{config.EMBEDDING_MODEL_REVISION} on device {config.EMBEDDING_DEVICE}: {exc}"
        ) from exc
    return _model


def get_model() -> SentenceTransformer:
    """Loads the pinned model once per process and reuses it on every
    subsequent call -- model loading is expensive and the model is
    stateless/thread-safe for encoding, so there's no reason to reload it."""
    return _load_model()


def reset_model_cache() -> None:
    """Test-only hook to force the next get_model() call to reload."""
    global _model
    _model = None


def _validate_vectors(vectors: list[list[float]]) -> None:
    for vector in vectors:
        if len(vector) != config.EMBEDDING_DIMENSION:
            raise ValueError(
                f"expected {config.EMBEDDING_DIMENSION}-dimensional vector, got {len(vector)}"
            )


def encode_documents(texts: list[str]) -> list[list[float]]:
    """Encodes canonical paper text (title + abstract + category) for
    storage. Never adds the query instruction prefix -- per the model card,
    passages must not receive it, only search queries."""
    if not texts:
        raise ValueError("texts must not be empty")
    for text in texts:
        if text is None or not text.strip():
            raise ValueError("document text must not be empty or whitespace-only")

    model = get_model()
    raw_vectors = model.encode(
        list(texts),
        batch_size=config.EMBEDDING_BATCH_SIZE,
        normalize_embeddings=config.EMBEDDING_NORMALIZE,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    vectors = [vector.tolist() for vector in raw_vectors]
    _validate_vectors(vectors)
    return vectors


def encode_query(query: str) -> list[float]:
    """Encodes a user search query, adding the configured BGE query
    instruction prefix exactly once. Never used for stored paper text."""
    if query is None or not query.strip():
        raise ValueError("query must not be empty or whitespace-only")

    model = get_model()
    prefixed_query = config.EMBEDDING_QUERY_PREFIX + query
    raw_vectors = model.encode(
        [prefixed_query],
        batch_size=config.EMBEDDING_BATCH_SIZE,
        normalize_embeddings=config.EMBEDDING_NORMALIZE,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    vector = raw_vectors[0].tolist()
    _validate_vectors([vector])
    return vector
