import re
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from research_platform.db.models import (
    Author,
    Category,
    Paper,
    PaperAuthor,
    PaperCategory,
    PaperSourceRecord,
    PaperVersion,
)
from research_platform.ingestion.normalize import build_version_rows

ARXIV_TAXONOMY_SOURCE = "arxiv"


def normalize_author_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().lower()


def get_or_create_category(session: Session, code: str) -> Category:
    category = session.execute(
        select(Category).where(Category.taxonomy_source == ARXIV_TAXONOMY_SOURCE, Category.code == code)
    ).scalar_one_or_none()
    if category is None:
        category = Category(taxonomy_source=ARXIV_TAXONOMY_SOURCE, code=code)
        session.add(category)
        session.flush()
    return category


def get_or_create_author(session: Session, display_name: str) -> Author:
    normalized_name = normalize_author_name(display_name)
    author = session.execute(
        select(Author).where(Author.source.is_(None), Author.normalized_name == normalized_name)
    ).scalar_one_or_none()
    if author is None:
        author = Author(source=None, source_author_id=None, display_name=display_name, normalized_name=normalized_name)
        session.add(author)
        session.flush()
    return author


def upsert_paper(session: Session, parsed: dict) -> tuple[Paper, bool]:
    """Idempotently upserts one parsed arXiv entry and all of its linked
    rows. Returns (paper, created) where created is True only when a new
    canonical paper row was inserted."""

    primary_category = get_or_create_category(session, parsed["primary_category"])
    secondary_categories = [get_or_create_category(session, code) for code in parsed["secondary_categories"]]

    paper = session.execute(select(Paper).where(Paper.arxiv_id == parsed["arxiv_id"])).scalar_one_or_none()
    created = paper is None

    if created:
        paper = Paper(
            arxiv_id=parsed["arxiv_id"],
            doi=parsed["doi"],
            normalized_title=parsed["normalized_title"],
            title=parsed["title"],
            abstract=parsed["abstract"],
            primary_category_id=primary_category.id,
            first_observed_source="arxiv",
            first_observed_at=datetime.now(timezone.utc),
            current_version_number=parsed["version_number"],
        )
        session.add(paper)
        session.flush()
    else:
        paper.doi = parsed["doi"] or paper.doi
        paper.normalized_title = parsed["normalized_title"]
        paper.title = parsed["title"]
        paper.abstract = parsed["abstract"]
        paper.primary_category_id = primary_category.id
        paper.current_version_number = parsed["version_number"]
        session.flush()

    _upsert_source_record(session, paper.id, parsed)
    _replace_versions(session, paper.id, parsed)
    _replace_categories(session, paper.id, primary_category, secondary_categories)
    _replace_authors(session, paper.id, parsed["authors"])

    return paper, created


def _upsert_source_record(session: Session, paper_id, parsed: dict) -> None:
    now = datetime.now(timezone.utc)
    stmt = pg_insert(PaperSourceRecord).values(
        paper_id=paper_id,
        source="arxiv",
        source_paper_id=parsed["arxiv_id"],
        raw_metadata=parsed["raw_metadata"],
        source_url=parsed["source_url"],
        pdf_url=parsed["pdf_url"],
        fetched_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["source", "source_paper_id"],
        set_={
            "raw_metadata": stmt.excluded.raw_metadata,
            "source_url": stmt.excluded.source_url,
            "pdf_url": stmt.excluded.pdf_url,
            "fetched_at": stmt.excluded.fetched_at,
            "updated_at": now,
        },
    )
    session.execute(stmt)


def _replace_versions(session: Session, paper_id, parsed: dict) -> None:
    session.execute(delete(PaperVersion).where(PaperVersion.paper_id == paper_id))
    session.flush()
    for row in build_version_rows(parsed):
        session.add(
            PaperVersion(
                paper_id=paper_id,
                source="arxiv",
                version_number=row["version_number"],
                version_identifier=row["version_identifier"],
                title=row["title"],
                abstract=row["abstract"],
                submitted_at=row["submitted_at"],
                content_verified=row["content_verified"],
                is_latest=row["is_latest"],
            )
        )
    session.flush()


def _replace_categories(session: Session, paper_id, primary_category: Category, secondary_categories: list[Category]) -> None:
    session.execute(delete(PaperCategory).where(PaperCategory.paper_id == paper_id))
    session.flush()
    session.add(PaperCategory(paper_id=paper_id, category_id=primary_category.id, is_primary=True))
    for category in secondary_categories:
        session.add(PaperCategory(paper_id=paper_id, category_id=category.id, is_primary=False))
    session.flush()


def _replace_authors(session: Session, paper_id, authors: list[dict]) -> None:
    session.execute(delete(PaperAuthor).where(PaperAuthor.paper_id == paper_id))
    session.flush()
    seen_author_ids = set()
    for entry in authors:
        author = get_or_create_author(session, entry["name"])
        if author.id in seen_author_ids:
            # Same normalized name appears twice in one paper's author list
            # (observed on a large-collaboration paper). paper_authors is
            # keyed on (paper_id, author_id), so keep only the first
            # occurrence's position rather than violating that constraint.
            continue
        seen_author_ids.add(author.id)
        session.add(
            PaperAuthor(
                paper_id=paper_id,
                author_id=author.id,
                author_order=entry["order"],
                affiliation_text_raw=None,
            )
        )
    session.flush()
