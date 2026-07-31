from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from research_platform.db.models import (
    Author,
    Category,
    Institution,
    Paper,
    PaperAuthor,
    PaperAuthorInstitution,
    PaperCategory,
    PaperEnrichmentMatch,
    PaperMetricSnapshot,
    PaperReference,
    PaperSourceRecord,
    PaperVenue,
    PaperVersion,
    PublicationVenue,
)
from research_platform.db.session import SessionLocal
from research_platform.enrichment.common import upsert_source_record_with_history
from research_platform.enrichment.openalex_matcher import match_paper
from research_platform.ingestion.run_tracker import IngestionRunTracker
from research_platform.ingestion.upsert import normalize_author_name

SOURCE = "openalex"
OPENALEX_TAXONOMY_SOURCE = "openalex"


def _get_publication_year(session, paper: Paper) -> int | None:
    v1 = session.execute(
        select(PaperVersion).where(PaperVersion.paper_id == paper.id, PaperVersion.version_number == 1)
    ).scalar_one_or_none()
    if v1 and v1.submitted_at:
        return v1.submitted_at.year
    return paper.first_observed_at.year if paper.first_observed_at else None


def _get_author_names(session, paper: Paper) -> list[str]:
    rows = (
        session.execute(
            select(Author.display_name)
            .join(PaperAuthor, PaperAuthor.author_id == Author.id)
            .where(PaperAuthor.paper_id == paper.id)
            .order_by(PaperAuthor.author_order)
        )
        .scalars()
        .all()
    )
    return list(rows)


def _upsert_match_record(session, paper_id, result: dict) -> None:
    now = datetime.now(timezone.utc)
    stmt = pg_insert(PaperEnrichmentMatch).values(
        paper_id=paper_id,
        source=SOURCE,
        match_status=result["match_status"],
        match_method=result["match_method"],
        confidence=result["confidence"],
        evidence=result["evidence"],
        matched_external_id=result["matched_external_id"],
        matching_rule_version=result["matching_rule_version"],
        attempted_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["paper_id", "source"],
        set_={
            "match_status": stmt.excluded.match_status,
            "match_method": stmt.excluded.match_method,
            "confidence": stmt.excluded.confidence,
            "evidence": stmt.excluded.evidence,
            "matched_external_id": stmt.excluded.matched_external_id,
            "matching_rule_version": stmt.excluded.matching_rule_version,
            "attempted_at": now,
            "updated_at": now,
        },
    )
    session.execute(stmt)


def _upsert_source_record(session, paper_id, work: dict) -> None:
    primary_location = work.get("primary_location") or {}
    upsert_source_record_with_history(
        session,
        paper_id=paper_id,
        source=SOURCE,
        source_paper_id=work.get("id"),
        raw_metadata=work,
        source_url=primary_location.get("landing_page_url"),
        pdf_url=primary_location.get("pdf_url"),
    )


def _record_citation_snapshot(session, paper_id, work: dict) -> bool:
    cited_by_count = work.get("cited_by_count")
    if cited_by_count is None:
        return False
    now = datetime.now(timezone.utc)
    stmt = pg_insert(PaperMetricSnapshot).values(
        paper_id=paper_id,
        metric_type="citation_count",
        source=SOURCE,
        value=cited_by_count,
        snapshot_date=now.date(),
        captured_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["paper_id", "metric_type", "source", "snapshot_date"],
        set_={"value": stmt.excluded.value, "captured_at": now},
    )
    session.execute(stmt)
    return True


def _resolve_cited_paper_id(session, openalex_work_id: str):
    return session.execute(
        select(PaperSourceRecord.paper_id).where(
            PaperSourceRecord.source == SOURCE, PaperSourceRecord.source_paper_id == openalex_work_id
        )
    ).scalar_one_or_none()


def _store_references(session, paper_id, work: dict) -> int:
    now = datetime.now(timezone.utc)
    count = 0
    for ref_id in work.get("referenced_works") or []:
        cited_paper_id = _resolve_cited_paper_id(session, ref_id)
        stmt = pg_insert(PaperReference).values(
            citing_paper_id=paper_id,
            cited_paper_id=cited_paper_id,
            cited_external_doi=None,
            cited_external_openalex_id=ref_id,
            cited_external_arxiv_id=None,
            source=SOURCE,
            discovered_at=now,
        )
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["citing_paper_id", "source", "cited_external_openalex_id"],
            index_where=text("cited_external_openalex_id IS NOT NULL"),
        )
        session.execute(stmt)
        count += 1
    return count


def _enrich_authors_and_institutions(session, paper_id, work: dict) -> dict:
    """Limited to source-record capture, per the explicit decision that
    full author disambiguation/merging is out of scope for this test. Only
    links an OpenAlex author identity to an existing arXiv-derived Author
    row when the normalized name matches exactly AND that identity isn't
    already claimed by a different Author row -- otherwise the author is
    left UNRESOLVED rather than risking an incorrect merge."""
    stats = {"authors_matched": 0, "authors_skipped": 0, "institutions_captured": 0}

    existing = session.execute(
        select(Author)
        .join(PaperAuthor, PaperAuthor.author_id == Author.id)
        .where(PaperAuthor.paper_id == paper_id)
    ).scalars().all()
    by_normalized_name = {a.normalized_name: a for a in existing}

    for authorship in work.get("authorships", []):
        oa_author = authorship.get("author") or {}
        oa_author_id = oa_author.get("id")
        oa_display_name = oa_author.get("display_name")
        if not oa_author_id or not oa_display_name:
            continue

        matching_author = by_normalized_name.get(normalize_author_name(oa_display_name))
        if matching_author is None:
            stats["authors_skipped"] += 1
            continue

        already_claimed = session.execute(
            select(Author.id).where(
                Author.source == SOURCE,
                Author.source_author_id == oa_author_id,
                Author.id != matching_author.id,
            )
        ).scalar_one_or_none()

        if matching_author.source is not None or already_claimed is not None:
            stats["authors_skipped"] += 1
            continue

        matching_author.source = SOURCE
        matching_author.source_author_id = oa_author_id
        matching_author.identity_status = "PROBABLE"
        matching_author.identity_confidence = 0.7
        session.add(matching_author)
        stats["authors_matched"] += 1

        for inst in authorship.get("institutions", []):
            inst_id, inst_name = inst.get("id"), inst.get("display_name")
            if not inst_id or not inst_name:
                continue
            institution = session.execute(
                select(Institution).where(
                    Institution.source == SOURCE, Institution.source_institution_id == inst_id
                )
            ).scalar_one_or_none()
            if institution is None:
                institution = Institution(
                    source=SOURCE,
                    source_institution_id=inst_id,
                    name=inst_name,
                    country_code=inst.get("country_code"),
                )
                session.add(institution)
                session.flush()
            link_exists = session.execute(
                select(PaperAuthorInstitution).where(
                    PaperAuthorInstitution.paper_id == paper_id,
                    PaperAuthorInstitution.author_id == matching_author.id,
                    PaperAuthorInstitution.institution_id == institution.id,
                )
            ).scalar_one_or_none()
            if link_exists is None:
                session.add(
                    PaperAuthorInstitution(
                        paper_id=paper_id, author_id=matching_author.id, institution_id=institution.id
                    )
                )
                stats["institutions_captured"] += 1

    return stats


def _enrich_venue(session, paper_id, work: dict) -> bool:
    source_info = (work.get("primary_location") or {}).get("source") or {}
    venue_id, venue_name = source_info.get("id"), source_info.get("display_name")
    if not venue_id or not venue_name:
        return False
    venue = session.execute(
        select(PublicationVenue).where(
            PublicationVenue.source == SOURCE, PublicationVenue.source_venue_id == venue_id
        )
    ).scalar_one_or_none()
    if venue is None:
        venue = PublicationVenue(
            source=SOURCE, source_venue_id=venue_id, name=venue_name, venue_type=source_info.get("type") or "unknown"
        )
        session.add(venue)
        session.flush()
    link_exists = session.execute(
        select(PaperVenue).where(PaperVenue.paper_id == paper_id, PaperVenue.venue_id == venue.id)
    ).scalar_one_or_none()
    if link_exists is None:
        session.add(PaperVenue(paper_id=paper_id, venue_id=venue.id, publication_date=None))
        return True
    return False


def _enrich_concepts(session, paper_id, work: dict) -> int:
    count = 0
    for concept in work.get("concepts") or []:
        concept_id, concept_name = concept.get("id"), concept.get("display_name")
        if not concept_id:
            continue
        category = session.execute(
            select(Category).where(
                Category.taxonomy_source == OPENALEX_TAXONOMY_SOURCE, Category.code == concept_id
            )
        ).scalar_one_or_none()
        if category is None:
            category = Category(taxonomy_source=OPENALEX_TAXONOMY_SOURCE, code=concept_id, display_name=concept_name)
            session.add(category)
            session.flush()
        link_exists = session.execute(
            select(PaperCategory).where(
                PaperCategory.paper_id == paper_id, PaperCategory.category_id == category.id
            )
        ).scalar_one_or_none()
        if link_exists is None:
            session.add(PaperCategory(paper_id=paper_id, category_id=category.id, is_primary=False))
            count += 1
    return count


def _store_enrichment_result(session, paper: Paper, result: dict) -> dict:
    """Pure DB-write phase -- safe to wrap in a SAVEPOINT. Must never be
    called with any network/pacing call inside it: pacing.py commits the
    session after every request, and committing while inside a SAVEPOINT
    block closes the outer transaction out from under it. The matching
    (network) phase must run before this, outside any nested transaction --
    see run_openalex_enrichment."""
    _upsert_match_record(session, paper.id, result)

    stats = {
        "arxiv_id": paper.arxiv_id,
        "match_status": result["match_status"],
        "match_method": result["match_method"],
        "references_stored": 0,
        "citation_snapshot_stored": False,
        "venue_added": False,
        "concepts_added": 0,
        "authors_matched": 0,
        "authors_skipped": 0,
        "institutions_captured": 0,
    }

    if result["match_status"] == "MATCHED":
        work = result["matched_work"]
        _upsert_source_record(session, paper.id, work)
        stats["citation_snapshot_stored"] = _record_citation_snapshot(session, paper.id, work)
        stats["references_stored"] = _store_references(session, paper.id, work)
        stats["venue_added"] = _enrich_venue(session, paper.id, work)
        stats["concepts_added"] = _enrich_concepts(session, paper.id, work)
        stats.update(_enrich_authors_and_institutions(session, paper.id, work))

    return stats


def run_openalex_enrichment(paper_ids: list) -> dict:
    """Enriches existing canonical papers only -- never creates a new
    papers row. Each paper is processed in its own SAVEPOINT so one
    failure never affects another paper's already-committed work."""
    session = SessionLocal()
    try:
        config_snapshot = {"paper_count": len(paper_ids)}
        per_paper_results = []
        with IngestionRunTracker(
            session, job_type="openalex_enrichment", config_snapshot=config_snapshot
        ) as tracker:
            for paper_id in paper_ids:
                tracker.record_processed()
                paper = session.get(Paper, paper_id)
                try:
                    author_names = _get_author_names(session, paper)
                    publication_year = _get_publication_year(session, paper)
                    result = match_paper(session, paper, author_names, publication_year)

                    with session.begin_nested():
                        stats = _store_enrichment_result(session, paper, result)
                    session.commit()
                    if stats["match_status"] == "MATCHED":
                        tracker.record_updated()
                    per_paper_results.append(stats)
                except Exception as exc:
                    session.rollback()
                    tracker.log_failure(
                        source=SOURCE,
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        source_identifier=str(paper_id),
                    )
                    per_paper_results.append(
                        {"arxiv_id": paper.arxiv_id if paper else None, "match_status": "EXCEPTION", "error": str(exc)}
                    )

        return {
            "run_id": str(tracker.run.id),
            "status": tracker.run.status,
            "processed": tracker.processed,
            "updated": tracker.updated,
            "failed": tracker.failed,
            "per_paper": per_paper_results,
        }
    finally:
        session.close()
