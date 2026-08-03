"""Validates the embedding-model wrapper: pinned revision/CPU device passed
to SentenceTransformer, document text never gets the query prefix, query
text gets it exactly once, batch size/normalization settings are honored,
invalid dimensions and model-load failures fail clearly, the model is loaded
once per process and reused, the SEMANTIC_SEARCH_MODE=local baked-path
branch is wired correctly, and sentence_transformers/torch are never
imported just by importing the FastAPI app. Fully mocked -- no real model
download, no network calls, no database writes. Run directly:

    python3 tests/test_embedding_model.py
"""
import subprocess
import sys
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np

from research_platform import config
from research_platform.embeddings import model as m

# SentenceTransformer is imported lazily inside m._load_model(), not at
# module level (see embeddings/model.py) -- there is no m.SentenceTransformer
# attribute to patch. Every test below patches the real import source
# instead, "sentence_transformers.SentenceTransformer", which the lazy
# `from sentence_transformers import SentenceTransformer` statement inside
# _load_model() resolves at call time, after the patch is already active.
_SENTENCE_TRANSFORMER_TARGET = "sentence_transformers.SentenceTransformer"


def _fake_encoder(dimension: int = 768):
    """Returns a fake SentenceTransformer whose .encode() produces
    deterministic, correctly-shaped, non-normalized-looking vectors (so
    normalization-flag tests can tell real behavior from a no-op)."""
    fake = MagicMock()

    def fake_encode(texts, batch_size, normalize_embeddings, convert_to_numpy, show_progress_bar):
        fake.last_call_kwargs = {
            "texts": list(texts),
            "batch_size": batch_size,
            "normalize_embeddings": normalize_embeddings,
            "convert_to_numpy": convert_to_numpy,
            "show_progress_bar": show_progress_bar,
        }
        return np.ones((len(texts), dimension), dtype="float32")

    fake.encode.side_effect = fake_encode
    return fake


def setup_function():
    m.reset_model_cache()


def test_pinned_revision_and_cpu_device_passed_on_load():
    captured_kwargs = {}

    def fake_constructor(model_name, revision, device):
        captured_kwargs["model_name"] = model_name
        captured_kwargs["revision"] = revision
        captured_kwargs["device"] = device
        return _fake_encoder()

    with patch(_SENTENCE_TRANSFORMER_TARGET, side_effect=fake_constructor):
        m.get_model()

    assert captured_kwargs["model_name"] == config.EMBEDDING_MODEL_NAME
    assert captured_kwargs["revision"] == config.EMBEDDING_MODEL_REVISION
    assert captured_kwargs["device"] == config.EMBEDDING_DEVICE == "cpu"
    print("PASS: pinned revision and CPU device passed to SentenceTransformer on load")


def test_document_text_receives_no_query_prefix():
    fake = _fake_encoder()
    with patch(_SENTENCE_TRANSFORMER_TARGET, return_value=fake):
        m.encode_documents(["Title: X\n\nAbstract: Y\n\nPrimary Category: cs.LG"])

    sent_text = fake.last_call_kwargs["texts"][0]
    assert config.EMBEDDING_QUERY_PREFIX not in sent_text
    assert sent_text == "Title: X\n\nAbstract: Y\n\nPrimary Category: cs.LG"
    print("PASS: document text sent to the model has no query prefix")


def test_query_text_receives_prefix_exactly_once():
    fake = _fake_encoder()
    with patch(_SENTENCE_TRANSFORMER_TARGET, return_value=fake):
        m.encode_query("graph neural networks")

    sent_text = fake.last_call_kwargs["texts"][0]
    assert sent_text == config.EMBEDDING_QUERY_PREFIX + "graph neural networks"
    assert sent_text.count(config.EMBEDDING_QUERY_PREFIX.strip()) == 1
    print("PASS: query text receives the BGE prefix exactly once")


def test_batch_size_and_normalization_settings_used():
    fake = _fake_encoder()
    with patch(_SENTENCE_TRANSFORMER_TARGET, return_value=fake):
        m.encode_documents(["doc one", "doc two"])

    assert fake.last_call_kwargs["batch_size"] == config.EMBEDDING_BATCH_SIZE
    assert fake.last_call_kwargs["normalize_embeddings"] == config.EMBEDDING_NORMALIZE
    print("PASS: configured batch size and normalize_embeddings flag passed through to encode()")


def test_invalid_dimensions_fail_clearly():
    fake = _fake_encoder(dimension=384)  # wrong dimension, simulating a misconfigured/wrong model
    with patch(_SENTENCE_TRANSFORMER_TARGET, return_value=fake):
        try:
            m.encode_documents(["some document text"])
            raised = False
        except ValueError as exc:
            raised = True
            message = str(exc)
    assert raised, "expected ValueError for wrong-dimension vectors"
    assert "768" in message and "384" in message
    print("PASS: wrong-dimension vectors fail clearly")


def test_empty_document_list_raises_value_error():
    try:
        m.encode_documents([])
        raised = False
    except ValueError:
        raised = True
    assert raised, "expected ValueError for empty document list"
    print("PASS: empty document list raises ValueError")


def test_empty_document_text_raises_value_error():
    for bad_text in (None, "", "   "):
        try:
            m.encode_documents([bad_text])
            raised = False
        except ValueError:
            raised = True
        assert raised, f"expected ValueError for document text={bad_text!r}"
    print("PASS: empty/whitespace-only document text raises ValueError")


def test_empty_query_raises_value_error():
    for bad_query in (None, "", "   "):
        try:
            m.encode_query(bad_query)
            raised = False
        except ValueError:
            raised = True
        assert raised, f"expected ValueError for query={bad_query!r}"
    print("PASS: empty/whitespace-only query raises ValueError")


def test_model_load_failure_raises_clear_error():
    def failing_constructor(*args, **kwargs):
        raise OSError("simulated network failure during model download")

    with patch(_SENTENCE_TRANSFORMER_TARGET, side_effect=failing_constructor):
        try:
            m.get_model()
            raised = False
        except m.EmbeddingModelLoadError as exc:
            raised = True
            message = str(exc)
    assert raised, "expected EmbeddingModelLoadError"
    assert config.EMBEDDING_MODEL_NAME in message
    assert config.EMBEDDING_MODEL_REVISION in message
    assert "simulated network failure" in message  # original exception preserved, not swallowed
    print("PASS: model-load failure raises a clear EmbeddingModelLoadError wrapping the cause")


def test_model_loaded_once_and_reused():
    construction_count = {"n": 0}

    def counting_constructor(*args, **kwargs):
        construction_count["n"] += 1
        return _fake_encoder()

    with patch(_SENTENCE_TRANSFORMER_TARGET, side_effect=counting_constructor):
        m.encode_documents(["doc one"])
        m.encode_documents(["doc two"])
        m.encode_query("some query")
        m.get_model()

    assert construction_count["n"] == 1, f"expected model constructed once, got {construction_count['n']}"
    print("PASS: model is loaded once per process and reused across calls")


def test_local_mode_loads_from_baked_path_without_hf_revision():
    captured_kwargs = {}

    def fake_constructor(model_name_or_path, **kwargs):
        captured_kwargs["model_name_or_path"] = model_name_or_path
        captured_kwargs.update(kwargs)
        return _fake_encoder()

    with tempfile.TemporaryDirectory() as baked_dir:
        with patch.object(config, "SEMANTIC_SEARCH_MODE", "local"), patch.object(
            config, "EMBEDDING_MODEL_LOCAL_PATH", baked_dir
        ), patch(_SENTENCE_TRANSFORMER_TARGET, side_effect=fake_constructor):
            m.get_model()

        assert captured_kwargs["model_name_or_path"] == baked_dir
        assert captured_kwargs["device"] == config.EMBEDDING_DEVICE == "cpu"
        assert captured_kwargs["local_files_only"] is True
        assert "revision" not in captured_kwargs
    print(
        "PASS: SEMANTIC_SEARCH_MODE=local loads from EMBEDDING_MODEL_LOCAL_PATH with "
        "local_files_only=True and no HF revision kwarg"
    )


def test_local_mode_missing_path_config_raises_clear_error():
    with patch.object(config, "SEMANTIC_SEARCH_MODE", "local"), patch.object(
        config, "EMBEDDING_MODEL_LOCAL_PATH", ""
    ):
        try:
            m.get_model()
            raised = False
        except m.EmbeddingModelLoadError as exc:
            raised = True
            message = str(exc)
    assert raised, "expected EmbeddingModelLoadError when EMBEDDING_MODEL_LOCAL_PATH is unset"
    assert "EMBEDDING_MODEL_LOCAL_PATH" in message
    print("PASS: local mode with no configured path fails clearly, before ever calling SentenceTransformer")


def test_local_mode_nonexistent_path_raises_clear_error():
    with patch.object(config, "SEMANTIC_SEARCH_MODE", "local"), patch.object(
        config, "EMBEDDING_MODEL_LOCAL_PATH", "/nonexistent/path/does/not/exist"
    ):
        try:
            m.get_model()
            raised = False
        except m.EmbeddingModelLoadError as exc:
            raised = True
            message = str(exc)
    assert raised, "expected EmbeddingModelLoadError for a nonexistent baked-model path"
    assert "/nonexistent/path/does/not/exist" in message
    print("PASS: local mode with a nonexistent baked-model path fails clearly")


def test_importing_api_app_does_not_load_torch():
    """Proves the sentence_transformers/torch import is actually lazy, not
    just "lazy in theory" -- runs in a fresh subprocess so an
    already-imported torch in THIS test process (e.g. from unittest.mock.
    patch resolving "sentence_transformers.SentenceTransformer" in the tests
    above, which does import the real package to find the attribute) can't
    produce a false pass. A placeholder DATABASE_URL is set only to satisfy
    config.py's import-time presence check -- never a real credential, and
    no database connection is actually attempted by importing the app
    module."""
    script = (
        "import os, sys\n"
        "os.environ.setdefault('DATABASE_URL', 'postgresql+psycopg2://user:pass@localhost/db')\n"
        "import research_platform.api.app\n"
        "print('TORCH_IN_SYS_MODULES=' + str('torch' in sys.modules))\n"
        "print('SENTENCE_TRANSFORMERS_IN_SYS_MODULES=' + str('sentence_transformers' in sys.modules))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"subprocess failed (exit {result.returncode}): {result.stderr}"
    assert "TORCH_IN_SYS_MODULES=False" in result.stdout, result.stdout
    assert "SENTENCE_TRANSFORMERS_IN_SYS_MODULES=False" in result.stdout, result.stdout
    print("PASS: importing research_platform.api.app does not import torch or sentence_transformers")


if __name__ == "__main__":
    test_pinned_revision_and_cpu_device_passed_on_load()
    setup_function()
    test_document_text_receives_no_query_prefix()
    setup_function()
    test_query_text_receives_prefix_exactly_once()
    setup_function()
    test_batch_size_and_normalization_settings_used()
    setup_function()
    test_invalid_dimensions_fail_clearly()
    setup_function()
    test_empty_document_list_raises_value_error()
    setup_function()
    test_empty_document_text_raises_value_error()
    setup_function()
    test_empty_query_raises_value_error()
    setup_function()
    test_model_load_failure_raises_clear_error()
    setup_function()
    test_model_loaded_once_and_reused()
    setup_function()
    test_local_mode_loads_from_baked_path_without_hf_revision()
    setup_function()
    test_local_mode_missing_path_config_raises_clear_error()
    setup_function()
    test_local_mode_nonexistent_path_raises_clear_error()
    setup_function()
    test_importing_api_app_does_not_load_torch()
    setup_function()
    print("\nALL TESTS PASSED")
