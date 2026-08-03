"""Validates embedding configuration loading and validation: correct
defaults, a genuinely immutable (full 40-hex commit sha) model revision --
not a placeholder or a mutable ref like "main" -- and clear failures on
invalid dimension/empty model name. No pytest dependency, no network calls,
no model download, no database writes. Run directly:

    python3 tests/test_embedding_config.py
"""
import re
import subprocess
import sys
from unittest.mock import patch

from research_platform import config

_FULL_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def test_defaults_load_correctly():
    assert config.EMBEDDING_MODEL_NAME == "BAAI/bge-base-en-v1.5"
    assert config.EMBEDDING_DIMENSION == 768
    assert config.EMBEDDING_DEVICE == "cpu"
    assert config.EMBEDDING_BATCH_SIZE == 16
    assert config.EMBEDDING_NORMALIZE is True
    assert config.EMBEDDING_QUERY_PREFIX == "Represent this sentence for searching relevant passages: "
    print("PASS: default embedding configuration values loaded correctly")


def test_revision_is_a_real_immutable_commit_sha_not_a_placeholder():
    revision = config.EMBEDDING_MODEL_REVISION
    assert _FULL_COMMIT_SHA_RE.match(revision), f"not a full 40-hex commit sha: {revision!r}"
    assert revision not in ("main", "master", "latest", "HEAD", ""), (
        f"revision must not be a mutable ref/placeholder: {revision!r}"
    )
    # The exact sha resolved from the Hugging Face model API for
    # BAAI/bge-base-en-v1.5 on 2026-07-29, cross-checked against both the
    # model's top-level `sha` field and its /revision/main endpoint.
    assert revision == "a5beb1e3e68b9ab74eb54cfd186867f64f240e1a"
    print("PASS: EMBEDDING_MODEL_REVISION is a real, immutable, resolved commit sha")


def test_validate_embedding_config_passes_on_defaults():
    config.validate_embedding_config()  # must not raise
    print("PASS: validate_embedding_config() accepts the default configuration")


def test_validate_rejects_empty_model_name():
    with patch.object(config, "EMBEDDING_MODEL_NAME", ""):
        try:
            config.validate_embedding_config()
            raised = False
        except ValueError as exc:
            raised = True
            message = str(exc)
    assert raised, "expected ValueError for empty EMBEDDING_MODEL_NAME"
    assert "EMBEDDING_MODEL_NAME" in message
    print("PASS: empty model name fails clearly")


def test_validate_rejects_whitespace_only_model_name():
    with patch.object(config, "EMBEDDING_MODEL_NAME", "   "):
        try:
            config.validate_embedding_config()
            raised = False
        except ValueError:
            raised = True
    assert raised, "expected ValueError for whitespace-only EMBEDDING_MODEL_NAME"
    print("PASS: whitespace-only model name fails clearly")


def test_validate_rejects_wrong_dimension():
    with patch.object(config, "EMBEDDING_DIMENSION", 384):
        try:
            config.validate_embedding_config()
            raised = False
        except ValueError as exc:
            raised = True
            message = str(exc)
    assert raised, "expected ValueError for EMBEDDING_DIMENSION != 768"
    assert "768" in message
    print("PASS: non-768 dimension fails clearly")


def test_validate_rejects_zero_or_negative_dimension():
    for bad_dim in (0, -768):
        with patch.object(config, "EMBEDDING_DIMENSION", bad_dim):
            try:
                config.validate_embedding_config()
                raised = False
            except ValueError:
                raised = True
        assert raised, f"expected ValueError for EMBEDDING_DIMENSION={bad_dim}"
    print("PASS: zero/negative dimension fails clearly")


def test_validate_rejects_mutable_revision_ref():
    for bad_revision in ("main", "master", "latest", "HEAD", "", "a5beb1e"):
        with patch.object(config, "EMBEDDING_MODEL_REVISION", bad_revision):
            try:
                config.validate_embedding_config()
                raised = False
            except ValueError:
                raised = True
        assert raised, f"expected ValueError for mutable/invalid revision {bad_revision!r}"
    print("PASS: mutable ref / short hash / empty revision all fail clearly")


def test_validate_rejects_non_positive_batch_size():
    for bad_batch in (0, -1):
        with patch.object(config, "EMBEDDING_BATCH_SIZE", bad_batch):
            try:
                config.validate_embedding_config()
                raised = False
            except ValueError:
                raised = True
        assert raised, f"expected ValueError for EMBEDDING_BATCH_SIZE={bad_batch}"
    print("PASS: non-positive batch size fails clearly")


def test_validate_rejects_empty_device():
    with patch.object(config, "EMBEDDING_DEVICE", ""):
        try:
            config.validate_embedding_config()
            raised = False
        except ValueError:
            raised = True
    assert raised, "expected ValueError for empty EMBEDDING_DEVICE"
    print("PASS: empty device fails clearly")


def test_query_prefix_is_distinct_and_only_intended_for_queries():
    # The model card is explicit that passages/documents must never receive
    # this prefix -- only search queries. This is a documentation-level
    # assertion at the config layer since no embedding-generation code
    # exists yet to exercise end-to-end.
    assert config.EMBEDDING_QUERY_PREFIX.strip() != ""
    assert "passages" in config.EMBEDDING_QUERY_PREFIX.lower()
    print("PASS: EMBEDDING_QUERY_PREFIX is a distinct, non-empty constant reserved for queries only")


# --- SEMANTIC_SEARCH_MODE / EMBEDDING_MODEL_LOCAL_PATH ----------------------
#
# validate_embedding_config() operates on the already-loaded, already-
# normalized module constants, so patch.object(config, ...) (auto-restoring,
# no shared-state leakage) is enough to test its logic directly -- same
# pattern the rest of this file already uses. Only the env-var-parsing
# behavior itself (trimming/lowercasing at import time) needs a fresh
# subprocess, since that code only runs once, at module import.


def test_semantic_search_mode_unset_or_empty_is_accepted_and_preserves_hf_hub_behavior():
    with patch.object(config, "SEMANTIC_SEARCH_MODE", ""):
        config.validate_embedding_config()  # must not raise
    print("PASS: SEMANTIC_SEARCH_MODE unset/empty is accepted (existing Hugging Face Hub download behavior)")


def test_semantic_search_mode_local_with_valid_path_is_accepted():
    with patch.object(config, "SEMANTIC_SEARCH_MODE", "local"), patch.object(
        config, "EMBEDDING_MODEL_LOCAL_PATH", "/opt/models/bge-base-en-v1.5"
    ):
        config.validate_embedding_config()  # must not raise
    print("PASS: SEMANTIC_SEARCH_MODE=local with a non-empty EMBEDDING_MODEL_LOCAL_PATH is accepted")


def test_semantic_search_mode_local_with_no_path_raises_clear_error():
    with patch.object(config, "SEMANTIC_SEARCH_MODE", "local"), patch.object(
        config, "EMBEDDING_MODEL_LOCAL_PATH", ""
    ):
        try:
            config.validate_embedding_config()
            raised = False
        except ValueError as exc:
            raised = True
            message = str(exc)
    assert raised, "expected ValueError for SEMANTIC_SEARCH_MODE=local with no EMBEDDING_MODEL_LOCAL_PATH"
    assert "EMBEDDING_MODEL_LOCAL_PATH" in message
    print("PASS: SEMANTIC_SEARCH_MODE=local with no path fails clearly, mentioning EMBEDDING_MODEL_LOCAL_PATH")


def test_semantic_search_mode_unsupported_value_raises_clear_error():
    for bad_mode in ("disabled", "remote", "invalid"):
        with patch.object(config, "SEMANTIC_SEARCH_MODE", bad_mode):
            try:
                config.validate_embedding_config()
                raised = False
            except ValueError as exc:
                raised = True
                message = str(exc)
        assert raised, f"expected ValueError for unsupported SEMANTIC_SEARCH_MODE={bad_mode!r}"
        assert "SEMANTIC_SEARCH_MODE" in message
    print("PASS: unsupported SEMANTIC_SEARCH_MODE values fail clearly, mentioning SEMANTIC_SEARCH_MODE")


def test_semantic_search_mode_env_var_is_trimmed_and_lowercased():
    """SEMANTIC_SEARCH_MODE is read once, at module-import time, via
    os.environ.get(...).strip().lower() -- verifying the actual
    environment-variable-parsing behavior (not just validate_embedding_
    config()'s logic on an already-normalized value, covered above) needs a
    fresh interpreter with the env var actually set before import. An
    isolated subprocess never mutates this test process's os.environ or
    reloads the shared config module object in sys.modules, so nothing
    leaks into later tests."""
    script = (
        "import os\n"
        "os.environ['SEMANTIC_SEARCH_MODE'] = ' LOCAL '\n"
        "os.environ.setdefault('DATABASE_URL', 'postgresql+psycopg2://user:pass@localhost/db')\n"
        "from research_platform import config\n"
        "print('MODE=' + repr(config.SEMANTIC_SEARCH_MODE))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"subprocess failed (exit {result.returncode}): {result.stderr}"
    assert "MODE='local'" in result.stdout, result.stdout
    print("PASS: SEMANTIC_SEARCH_MODE env var is trimmed and lowercased at import time (' LOCAL ' -> 'local')")


if __name__ == "__main__":
    test_defaults_load_correctly()
    test_revision_is_a_real_immutable_commit_sha_not_a_placeholder()
    test_validate_embedding_config_passes_on_defaults()
    test_validate_rejects_empty_model_name()
    test_validate_rejects_whitespace_only_model_name()
    test_validate_rejects_wrong_dimension()
    test_validate_rejects_zero_or_negative_dimension()
    test_validate_rejects_mutable_revision_ref()
    test_validate_rejects_non_positive_batch_size()
    test_validate_rejects_empty_device()
    test_query_prefix_is_distinct_and_only_intended_for_queries()
    test_semantic_search_mode_unset_or_empty_is_accepted_and_preserves_hf_hub_behavior()
    test_semantic_search_mode_local_with_valid_path_is_accepted()
    test_semantic_search_mode_local_with_no_path_raises_clear_error()
    test_semantic_search_mode_unsupported_value_raises_clear_error()
    test_semantic_search_mode_env_var_is_trimmed_and_lowercased()
    print("\nALL TESTS PASSED")
