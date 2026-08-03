import os
from typing import TYPE_CHECKING

from research_platform import config

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

# sentence_transformers (and, transitively, torch) is deliberately NOT
# imported at module level -- only inside _load_model(), the first time a
# real encode actually happens. Importing research_platform.api.app (which
# imports this module transitively, to reach encode_query/encode_documents)
# must not pay torch's import cost just to serve /health, /api/v1/clusters,
# /api/v1/trends/*, etc. -- most requests never touch the embedding model at
# all, and on Cloud Run (min instances 0) that's real cold-start latency for
# no benefit. See test_importing_api_app_does_not_load_torch in
# tests/test_embedding_model.py.
_model: "SentenceTransformer | None" = None


class EmbeddingModelError(Exception):
    pass


class EmbeddingModelLoadError(EmbeddingModelError):
    """Raised when the pinned model fails to load (bad revision, no network
    on first download, corrupted cache, etc), or when SEMANTIC_SEARCH_MODE
    is "local" but EMBEDDING_MODEL_LOCAL_PATH is missing/misconfigured.
    Wraps the original exception rather than swallowing it."""


def _load_model() -> "SentenceTransformer":
    global _model
    if _model is not None:
        return _model

    from sentence_transformers import SentenceTransformer

    if config.SEMANTIC_SEARCH_MODE == "local":
        if not os.path.isdir(config.EMBEDDING_MODEL_LOCAL_PATH):
            raise EmbeddingModelLoadError(
                "SEMANTIC_SEARCH_MODE=local but EMBEDDING_MODEL_LOCAL_PATH does not exist or "
                f"is not a directory: {config.EMBEDDING_MODEL_LOCAL_PATH!r}"
            )
        try:
            # A baked local path is a self-contained snapshot -- no HF Hub
            # revision concept applies. local_files_only=True guarantees no
            # network call happens here even if the path merely looks like
            # a HF cache layout -- Cloud Run's baked image has no need for
            # (and, depending on network policy, may not have) egress.
            _model = SentenceTransformer(
                config.EMBEDDING_MODEL_LOCAL_PATH,
                device=config.EMBEDDING_DEVICE,
                local_files_only=True,
            )
        except Exception as exc:
            raise EmbeddingModelLoadError(
                f"failed to load baked embedding model from {config.EMBEDDING_MODEL_LOCAL_PATH!r} "
                f"on device {config.EMBEDDING_DEVICE}: {exc}"
            ) from exc
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


def get_model() -> "SentenceTransformer":
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
