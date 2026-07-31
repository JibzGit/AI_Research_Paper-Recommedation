"""Validates the canonical paper-text builder used for embeddings: fixed
format, whitespace normalization, deterministic SHA-256 hashing, no
mutation of caller input, no BGE query prefix, and clear failures on
missing title/abstract. No pytest dependency, no network calls, no model
download, no database writes. Run directly:

    python3 tests/test_canonical_text.py
"""
import hashlib

from research_platform import config
from research_platform.embeddings.canonical_text import build_canonical_text


def test_normal_title_abstract_category():
    result = build_canonical_text("Deep Learning for Graphs", "We study graph neural networks.", "cs.LG")
    assert result.canonical_text == (
        "Title: Deep Learning for Graphs\n\n"
        "Abstract: We study graph neural networks.\n\n"
        "Primary Category: cs.LG"
    )
    print("PASS: normal title/abstract/category produce the exact expected format")


def test_leading_trailing_whitespace_removed():
    result = build_canonical_text(
        "  Deep Learning for Graphs  ", "  We study graph neural networks.  ", "  cs.LG  "
    )
    assert result.canonical_text == (
        "Title: Deep Learning for Graphs\n\n"
        "Abstract: We study graph neural networks.\n\n"
        "Primary Category: cs.LG"
    )
    print("PASS: leading/trailing whitespace stripped from all three fields")


def test_repeated_spaces_and_line_breaks_normalized():
    title = "Deep   Learning\tfor Graphs"
    abstract = "We study graph\nneural   networks.\r\nIt works well."
    category = "cs.LG"
    result = build_canonical_text(title, abstract, category)
    assert "Title: Deep Learning for Graphs\n\n" in result.canonical_text
    assert "Abstract: We study graph neural networks. It works well.\n\n" in result.canonical_text
    assert "  " not in result.canonical_text.replace("\n\n", "")  # no double-spaces outside the format separators
    print("PASS: repeated internal whitespace and line breaks collapsed to single spaces")


def test_deterministic_text_output():
    args = ("Deep Learning for Graphs", "We study graph neural networks.", "cs.LG")
    result_a = build_canonical_text(*args)
    result_b = build_canonical_text(*args)
    assert result_a.canonical_text == result_b.canonical_text
    print("PASS: identical inputs produce identical canonical_text")


def test_deterministic_hash_output():
    args = ("Deep Learning for Graphs", "We study graph neural networks.", "cs.LG")
    result_a = build_canonical_text(*args)
    result_b = build_canonical_text(*args)
    assert result_a.source_text_hash == result_b.source_text_hash
    expected = hashlib.sha256(result_a.canonical_text.encode("utf-8")).hexdigest()
    assert result_a.source_text_hash == expected
    print("PASS: identical inputs produce identical, correctly-computed SHA-256 hash")


def test_harmless_whitespace_differences_produce_same_hash():
    result_a = build_canonical_text("Deep Learning for Graphs", "We study graph neural networks.", "cs.LG")
    result_b = build_canonical_text(
        "  Deep   Learning for Graphs  ", "We study graph\nneural networks.   ", "  cs.LG"
    )
    assert result_a.canonical_text == result_b.canonical_text
    assert result_a.source_text_hash == result_b.source_text_hash
    print("PASS: harmless whitespace differences collapse to the same text and hash")


def test_different_abstract_produces_different_hash():
    result_a = build_canonical_text("Same Title", "Abstract one.", "cs.LG")
    result_b = build_canonical_text("Same Title", "Abstract two.", "cs.LG")
    assert result_a.source_text_hash != result_b.source_text_hash
    print("PASS: different abstract produces a different hash")


def test_different_title_produces_different_hash():
    result_a = build_canonical_text("Title One", "Same abstract.", "cs.LG")
    result_b = build_canonical_text("Title Two", "Same abstract.", "cs.LG")
    assert result_a.source_text_hash != result_b.source_text_hash
    print("PASS: different title produces a different hash")


def test_missing_category_falls_back_to_unknown():
    for missing in (None, "", "   "):
        result = build_canonical_text("Some Title", "Some abstract.", missing)
        assert "Primary Category: Unknown" in result.canonical_text, f"failed for category={missing!r}"
    print("PASS: missing/empty/whitespace-only category falls back to 'Unknown'")


def test_empty_title_raises_value_error():
    for bad_title in (None, "", "   "):
        try:
            build_canonical_text(bad_title, "Some abstract.", "cs.LG")
            raised = False
        except ValueError as exc:
            raised = True
            message = str(exc)
        assert raised, f"expected ValueError for title={bad_title!r}"
        assert "title" in message.lower()
    print("PASS: empty/None/whitespace-only title raises a clear ValueError")


def test_empty_abstract_raises_value_error():
    for bad_abstract in (None, "", "   "):
        try:
            build_canonical_text("Some Title", bad_abstract, "cs.LG")
            raised = False
        except ValueError as exc:
            raised = True
            message = str(exc)
        assert raised, f"expected ValueError for abstract={bad_abstract!r}"
        assert "abstract" in message.lower()
    print("PASS: empty/None/whitespace-only abstract raises a clear ValueError")


def test_original_input_not_mutated():
    original_title = "  Deep   Learning  "
    original_abstract = "  We study\ngraphs.  "
    original_category = "  cs.LG  "
    build_canonical_text(original_title, original_abstract, original_category)
    assert original_title == "  Deep   Learning  "
    assert original_abstract == "  We study\ngraphs.  "
    assert original_category == "  cs.LG  "
    print("PASS: original input strings are not mutated")


def test_query_prefix_not_included_in_stored_text():
    result = build_canonical_text("Deep Learning for Graphs", "We study graph neural networks.", "cs.LG")
    assert config.EMBEDDING_QUERY_PREFIX not in result.canonical_text
    print("PASS: BGE query prefix is never included in stored paper text")


if __name__ == "__main__":
    test_normal_title_abstract_category()
    test_leading_trailing_whitespace_removed()
    test_repeated_spaces_and_line_breaks_normalized()
    test_deterministic_text_output()
    test_deterministic_hash_output()
    test_harmless_whitespace_differences_produce_same_hash()
    test_different_abstract_produces_different_hash()
    test_different_title_produces_different_hash()
    test_missing_category_falls_back_to_unknown()
    test_empty_title_raises_value_error()
    test_empty_abstract_raises_value_error()
    test_original_input_not_mutated()
    test_query_prefix_not_included_in_stored_text()
    print("\nALL TESTS PASSED")
