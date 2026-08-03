import os
import re

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ["DATABASE_URL"]

# arXiv request pacing (persisted in api_request_states, shared across processes)
ARXIV_BASE_DELAY_SECONDS = float(os.environ.get("ARXIV_BASE_DELAY_SECONDS", "5"))
ARXIV_JITTER_MAX_SECONDS = float(os.environ.get("ARXIV_JITTER_MAX_SECONDS", "2"))
ARXIV_MAX_RETRIES = int(os.environ.get("ARXIV_MAX_RETRIES", "5"))
ARXIV_MAX_COOLDOWN_SECONDS = float(os.environ.get("ARXIV_MAX_COOLDOWN_SECONDS", str(15 * 60)))
ARXIV_RATE_LIMIT_BASELINE_SECONDS = float(os.environ.get("ARXIV_RATE_LIMIT_BASELINE_SECONDS", "30"))
ARXIV_TEMPORARY_ERROR_BASELINE_SECONDS = float(os.environ.get("ARXIV_TEMPORARY_ERROR_BASELINE_SECONDS", "10"))

# Historical backfill / quota ingestion
ARXIV_DEFAULT_PAGE_SIZE = int(os.environ.get("ARXIV_DEFAULT_PAGE_SIZE", "200"))
BACKFILL_START_DATE = os.environ.get("BACKFILL_START_DATE", "2016-01-01")

# Semantic Scholar: a secret. Never print, log, or otherwise expose this value.
SEMANTIC_SCHOLAR_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or None
SEMANTIC_SCHOLAR_BASE_DELAY_SECONDS = float(os.environ.get("SEMANTIC_SCHOLAR_BASE_DELAY_SECONDS", "1.1"))
SEMANTIC_SCHOLAR_JITTER_MAX_SECONDS = float(os.environ.get("SEMANTIC_SCHOLAR_JITTER_MAX_SECONDS", "2"))
SEMANTIC_SCHOLAR_MAX_RETRIES = int(os.environ.get("SEMANTIC_SCHOLAR_MAX_RETRIES", "5"))
SEMANTIC_SCHOLAR_MAX_COOLDOWN_SECONDS = float(os.environ.get("SEMANTIC_SCHOLAR_MAX_COOLDOWN_SECONDS", "900"))
SEMANTIC_SCHOLAR_429_BASELINE_SECONDS = float(os.environ.get("SEMANTIC_SCHOLAR_429_BASELINE_SECONDS", "30"))
SEMANTIC_SCHOLAR_TEMPORARY_ERROR_BASELINE_SECONDS = float(
    os.environ.get("SEMANTIC_SCHOLAR_TEMPORARY_ERROR_BASELINE_SECONDS", "10")
)


def semantic_scholar_api_key_status() -> str:
    """Never returns or logs the key itself -- only whether one is set."""
    return "configured" if SEMANTIC_SCHOLAR_API_KEY else "not configured"


# OpenAlex: a secret. Never print, log, or otherwise expose this value.
# Required as of the 2026-07-29 budget-exhaustion incident -- OpenAlex
# execution must not be attempted without a key (see openalex_client.py's
# OpenAlexMissingApiKeyError).
OPENALEX_API_KEY = os.environ.get("OPENALEX_API_KEY") or None


def openalex_api_key_status() -> str:
    """Never returns or logs the key itself -- only whether one is set."""
    return "configured" if OPENALEX_API_KEY else "not configured"


# --- Embedding model (paper-level embeddings / semantic search) -----------
#
# EMBEDDING_MODEL_REVISION is pinned to the exact immutable commit sha of
# BAAI/bge-base-en-v1.5 on Hugging Face, resolved 2026-07-29 via the HF
# model API (https://huggingface.co/api/models/BAAI/bge-base-en-v1.5),
# cross-checked against the /revision/main endpoint -- both returned the
# same sha. This is a real commit hash, not a mutable ref like "main", so
# the exact model weights this pins to cannot silently change under us.
EMBEDDING_MODEL_NAME = os.environ.get("EMBEDDING_MODEL_NAME", "BAAI/bge-base-en-v1.5")
EMBEDDING_MODEL_REVISION = os.environ.get(
    "EMBEDDING_MODEL_REVISION", "a5beb1e3e68b9ab74eb54cfd186867f64f240e1a"
)
EMBEDDING_DIMENSION = int(os.environ.get("EMBEDDING_DIMENSION", "768"))
EMBEDDING_DEVICE = os.environ.get("EMBEDDING_DEVICE", "cpu")
EMBEDDING_BATCH_SIZE = int(os.environ.get("EMBEDDING_BATCH_SIZE", "16"))
EMBEDDING_NORMALIZE = os.environ.get("EMBEDDING_NORMALIZE", "true").strip().lower() in (
    "1", "true", "yes",
)
# Official bge-base-en-v1.5 model-card guidance (README.md "Model List"
# table, same pinned revision): prepend this instruction to search QUERIES
# only. Stored passages/documents (title+abstract+category) must NOT use
# it -- the model card is explicit that "no instruction needs to be added
# to passages."
EMBEDDING_QUERY_PREFIX = os.environ.get(
    "EMBEDDING_QUERY_PREFIX", "Represent this sentence for searching relevant passages: "
)

# SEMANTIC_SEARCH_MODE controls where the model loads from. Unset (default,
# "") preserves existing local/dev behavior exactly: SentenceTransformer
# downloads/caches EMBEDDING_MODEL_NAME @ EMBEDDING_MODEL_REVISION from the
# Hugging Face Hub. "local" is for containerized deployments (Cloud Run)
# that bake the model into the image at build time -- see
# embeddings/model.py -- and load it from EMBEDDING_MODEL_LOCAL_PATH
# instead, with no network call at model-load time.
SEMANTIC_SEARCH_MODE = os.environ.get("SEMANTIC_SEARCH_MODE", "").strip().lower()
EMBEDDING_MODEL_LOCAL_PATH = os.environ.get("EMBEDDING_MODEL_LOCAL_PATH", "").strip()

_FULL_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def validate_embedding_config() -> None:
    """Raises ValueError with a clear, specific message on any invalid
    embedding configuration. Not called automatically at import time (mirrors
    the rest of this module: constants are always loaded, validation is
    explicit) -- call this before any code path that will actually load the
    model or write to paper_embeddings."""
    if not EMBEDDING_MODEL_NAME or not EMBEDDING_MODEL_NAME.strip():
        raise ValueError("EMBEDDING_MODEL_NAME must not be empty")

    if not _FULL_COMMIT_SHA_RE.match(EMBEDDING_MODEL_REVISION):
        raise ValueError(
            "EMBEDDING_MODEL_REVISION must be a full 40-character immutable Hugging Face "
            f"commit sha (e.g. not a mutable ref like 'main'); got {EMBEDDING_MODEL_REVISION!r}"
        )

    if EMBEDDING_DIMENSION != 768:
        raise ValueError(
            "EMBEDDING_DIMENSION must be 768 -- it must match the paper_embeddings.embedding "
            f"column, which is a fixed VECTOR(768); got {EMBEDDING_DIMENSION}"
        )

    if EMBEDDING_BATCH_SIZE <= 0:
        raise ValueError(f"EMBEDDING_BATCH_SIZE must be a positive integer; got {EMBEDDING_BATCH_SIZE}")

    if not EMBEDDING_DEVICE or not EMBEDDING_DEVICE.strip():
        raise ValueError("EMBEDDING_DEVICE must not be empty")

    if SEMANTIC_SEARCH_MODE not in ("", "local"):
        raise ValueError(
            f"SEMANTIC_SEARCH_MODE must be empty (Hugging Face Hub download) or 'local' "
            f"(baked local path); got {SEMANTIC_SEARCH_MODE!r}"
        )

    if SEMANTIC_SEARCH_MODE == "local" and not EMBEDDING_MODEL_LOCAL_PATH:
        raise ValueError("EMBEDDING_MODEL_LOCAL_PATH must be set when SEMANTIC_SEARCH_MODE=local")


# --- LLM cluster labeling ---------------------------------------------------
#
# Anthropic: a secret. Never print, log, or otherwise expose this value.
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY") or None


def anthropic_api_key_status() -> str:
    """Never returns or logs the key itself -- only whether one is set."""
    return "configured" if ANTHROPIC_API_KEY else "not configured"


CLUSTER_LABEL_PRIMARY_PROVIDER = os.environ.get("CLUSTER_LABEL_PRIMARY_PROVIDER", "anthropic")
CLUSTER_LABEL_PRIMARY_MODEL = os.environ.get("CLUSTER_LABEL_PRIMARY_MODEL", "claude-haiku-4-5-20251001")
CLUSTER_LABEL_FALLBACK_PROVIDER = os.environ.get("CLUSTER_LABEL_FALLBACK_PROVIDER", "anthropic")
CLUSTER_LABEL_FALLBACK_MODEL = os.environ.get("CLUSTER_LABEL_FALLBACK_MODEL", "claude-sonnet-5")

CLUSTER_LABEL_MAX_RETRIES = int(os.environ.get("CLUSTER_LABEL_MAX_RETRIES", "3"))
CLUSTER_LABEL_TIMEOUT_SECONDS = float(os.environ.get("CLUSTER_LABEL_TIMEOUT_SECONDS", "30"))
CLUSTER_LABEL_BASE_BACKOFF_SECONDS = float(os.environ.get("CLUSTER_LABEL_BASE_BACKOFF_SECONDS", "2"))


# --- API / CORS --------------------------------------------------------------
#
# Comma-separated list of origins allowed to call the API cross-origin (the
# Vite frontend dev server by default). Never combined with credentialed
# requests -- see app.py, where allow_credentials is hardcoded False -- so a
# wildcard here could never be paired with allow_credentials=True even by
# future misconfiguration of this variable alone.
CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
