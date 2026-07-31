import hashlib
import re
from typing import NamedTuple

_WHITESPACE_RE = re.compile(r"\s+")

UNKNOWN_CATEGORY = "Unknown"


class CanonicalTextResult(NamedTuple):
    canonical_text: str
    source_text_hash: str


def _clean(value: str) -> str:
    """Strips leading/trailing whitespace and collapses any run of internal
    whitespace (spaces, tabs, line breaks of any style) to a single space.
    Never mutates the caller's string -- str is immutable in Python, and
    this always returns a new string rather than modifying in place."""
    return _WHITESPACE_RE.sub(" ", value).strip()


def build_canonical_text(title: str, abstract: str, primary_category: str | None) -> CanonicalTextResult:
    """Builds the canonical text used for paper embeddings: title + abstract
    + primary category, in a fixed format, with normalized whitespace. Never
    includes the BGE query-instruction prefix -- that prefix is applied only
    to user search queries at query time (see EMBEDDING_QUERY_PREFIX in
    config.py), never to stored document text.

    title and abstract are required and must not be empty (after stripping
    whitespace) -- a paper with no title or abstract has nothing meaningful
    to embed, so this fails loudly rather than silently embedding a
    near-empty text. primary_category is optional and falls back to
    "Unknown" if missing or empty, since a missing category doesn't make
    the rest of the text meaningless.
    """
    if title is None or not title.strip():
        raise ValueError("title is required and must not be empty")
    if abstract is None or not abstract.strip():
        raise ValueError("abstract is required and must not be empty")

    cleaned_title = _clean(title)
    cleaned_abstract = _clean(abstract)
    cleaned_category = _clean(primary_category) if primary_category and primary_category.strip() else UNKNOWN_CATEGORY

    canonical_text = (
        f"Title: {cleaned_title}\n\n"
        f"Abstract: {cleaned_abstract}\n\n"
        f"Primary Category: {cleaned_category}"
    )
    source_text_hash = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()

    return CanonicalTextResult(canonical_text=canonical_text, source_text_hash=source_text_hash)
