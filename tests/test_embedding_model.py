"""Validates the embedding-model wrapper: pinned revision/CPU device passed
to SentenceTransformer, document text never gets the query prefix, query
text gets it exactly once, batch size/normalization settings are honored,
invalid dimensions and model-load failures fail clearly, and the model is
loaded once per process and reused. Fully mocked -- no real model download,
no network calls, no database writes. Run directly:

    python3 tests/test_embedding_model.py
"""
from unittest.mock import MagicMock, patch

import numpy as np

from research_platform import config
from research_platform.embeddings import model as m


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

    with patch.object(m, "SentenceTransformer", side_effect=fake_constructor):
        m.get_model()

    assert captured_kwargs["model_name"] == config.EMBEDDING_MODEL_NAME
    assert captured_kwargs["revision"] == config.EMBEDDING_MODEL_REVISION
    assert captured_kwargs["device"] == config.EMBEDDING_DEVICE == "cpu"
    print("PASS: pinned revision and CPU device passed to SentenceTransformer on load")


def test_document_text_receives_no_query_prefix():
    fake = _fake_encoder()
    with patch.object(m, "SentenceTransformer", return_value=fake):
        m.encode_documents(["Title: X\n\nAbstract: Y\n\nPrimary Category: cs.LG"])

    sent_text = fake.last_call_kwargs["texts"][0]
    assert config.EMBEDDING_QUERY_PREFIX not in sent_text
    assert sent_text == "Title: X\n\nAbstract: Y\n\nPrimary Category: cs.LG"
    print("PASS: document text sent to the model has no query prefix")


def test_query_text_receives_prefix_exactly_once():
    fake = _fake_encoder()
    with patch.object(m, "SentenceTransformer", return_value=fake):
        m.encode_query("graph neural networks")

    sent_text = fake.last_call_kwargs["texts"][0]
    assert sent_text == config.EMBEDDING_QUERY_PREFIX + "graph neural networks"
    assert sent_text.count(config.EMBEDDING_QUERY_PREFIX.strip()) == 1
    print("PASS: query text receives the BGE prefix exactly once")


def test_batch_size_and_normalization_settings_used():
    fake = _fake_encoder()
    with patch.object(m, "SentenceTransformer", return_value=fake):
        m.encode_documents(["doc one", "doc two"])

    assert fake.last_call_kwargs["batch_size"] == config.EMBEDDING_BATCH_SIZE
    assert fake.last_call_kwargs["normalize_embeddings"] == config.EMBEDDING_NORMALIZE
    print("PASS: configured batch size and normalize_embeddings flag passed through to encode()")


def test_invalid_dimensions_fail_clearly():
    fake = _fake_encoder(dimension=384)  # wrong dimension, simulating a misconfigured/wrong model
    with patch.object(m, "SentenceTransformer", return_value=fake):
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

    with patch.object(m, "SentenceTransformer", side_effect=failing_constructor):
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

    with patch.object(m, "SentenceTransformer", side_effect=counting_constructor):
        m.encode_documents(["doc one"])
        m.encode_documents(["doc two"])
        m.encode_query("some query")
        m.get_model()

    assert construction_count["n"] == 1, f"expected model constructed once, got {construction_count['n']}"
    print("PASS: model is loaded once per process and reused across calls")


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
    print("\nALL TESTS PASSED")
