from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from research_platform.db.models import (
    Author,
    Institution,
    Paper,
    PaperAuthor,
    PaperAuthorInstitution,
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
from research_platform.enrichment.semantic_scholar_matcher import match_paper
from research_platform.ingestion.run_tracker import IngestionRunTracker
from research_platform.ingestion.upsert import normalize_author_name

SOURCE = "semantic_scholar"


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


def _known_s2_id(session, paper_id) -> str | None:
    return session.execute(
        select(PaperSourceRecord.source_paper_id).where(
            PaperSourceRecord.paper_id == paper_id, PaperSourceRecord.source == SOURCE
        )
    ).scalar_one_or_none()


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


def _upsert_source_record(session, paper_id, s2_paper: dict) -> None:
    paper_s2_id = s2_paper.get("paperId")
    upsert_source_record_with_history(
        session,
        paper_id=paper_id,
        source=SOURCE,
        source_paper_id=paper_s2_id,
        raw_metadata=s2_paper,
        source_url=f"https://www.semanticscholar.org/paper/{paper_s2_id}" if paper_s2_id else None,
        pdf_url=None,
    )


def _record_citation_snapshot(session, paper_id, s2_paper: dict) -> bool:
    citation_count = s2_paper.get("citationCount")
    if citation_count is None:
        return False
    now = datetime.now(timezone.utc)
    stmt = pg_insert(PaperMetricSnapshot).values(
        paper_id=paper_id,
        metric_type="citation_count",
        source=SOURCE,
        value=citation_count,
        snapshot_date=now.date(),
        captured_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["paper_id", "metric_type", "source", "snapshot_date"],
        set_={"value": stmt.excluded.value, "captured_at": now},
    )
    session.execute(stmt)
    return True


def _resolve_cited_paper_id(session, source_external_id: str):
    return session.execute(
        select(PaperSourceRecord.paper_id).where(
            PaperSourceRecord.source == SOURCE, PaperSourceRecord.source_paper_id == source_external_id
        )
    ).scalar_one_or_none()


def _store_references(session, paper_id, s2_paper: dict) -> int:
    """Reuses the existing cited_external_openalex_id column to hold the
    citing source's own external ID for the referenced work when
    source != 'openalex' (here, S2's paperId). This is a naming artifact
    from when only OpenAlex existed -- the partial unique index includes
    `source`, so per-source dedup is still correct; a future migration
    could rename the column for clarity, but no schema change was made
    here per the instruction to reuse the existing architecture as-is."""
    now = datetime.now(timezone.utc)
    count = 0
    for ref in s2_paper.get("references") or []:
        ref_s2_id = ref.get("paperId")
        if not ref_s2_id:
            continue
        ref_external_ids = ref.get("externalIds") or {}
        cited_paper_id = _resolve_cited_paper_id(session, ref_s2_id)
        stmt = pg_insert(PaperReference).values(
            citing_paper_id=paper_id,
            cited_paper_id=cited_paper_id,
            cited_external_doi=ref_external_ids.get("DOI"),
            cited_external_openalex_id=ref_s2_id,
            cited_external_arxiv_id=ref_external_ids.get("ArXiv"),
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


def _enrich_authors_and_institutions(session, paper_id, s2_paper: dict) -> dict:
    """Source-record capture only, same conservative policy as OpenAlex:
    only links an S2 author identity to an existing arXiv-derived Author
    row on an exact normalized-name match not already claimed by another
    source. S2's affiliations are plain strings (no structured institution
    IDs), so the affiliation string itself is used as source_institution_id
    -- less structured than OpenAlex's ROR-linked institutions, but a
    reasonable natural key for a first pass."""
    stats = {"authors_matched": 0, "authors_skipped": 0, "institutions_captured": 0}

    existing = session.execute(
        select(Author)
        .join(PaperAuthor, PaperAuthor.author_id == Author.id)
        .where(PaperAuthor.paper_id == paper_id)
    ).scalars().all()
    by_normalized_name = {a.normalized_name: a for a in existing}

    for s2_author in s2_paper.get("authors") or []:
        s2_author_id = s2_author.get("authorId")
        s2_name = s2_author.get("name")
        if not s2_author_id or not s2_name:
            continue

        matching_author = by_normalized_name.get(normalize_author_name(s2_name))
        if matching_author is None:
            stats["authors_skipped"] += 1
            continue

        already_claimed = session.execute(
            select(Author.id).where(
                Author.source == SOURCE, Author.source_author_id == s2_author_id, Author.id != matching_author.id
            )
        ).scalar_one_or_none()

        if matching_author.source is not None or already_claimed is not None:
            stats["authors_skipped"] += 1
            continue

        matching_author.source = SOURCE
        matching_author.source_author_id = s2_author_id
        matching_author.identity_status = "PROBABLE"
        matching_author.identity_confidence = 0.7
        session.add(matching_author)
        stats["authors_matched"] += 1

        for affiliation in s2_author.get("affiliations") or []:
            if not affiliation:
                continue
            institution = session.execute(
                select(Institution).where(
                    Institution.source == SOURCE, Institution.source_institution_id == affiliation
                )
            ).scalar_one_or_none()
            if institution is None:
                institution = Institution(
                    source=SOURCE, source_institution_id=affiliation, name=affiliation, country_code=None
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


def _enrich_venue(session, paper_id, s2_paper: dict) -> bool:
    venue_name = s2_paper.get("venue")
    if not venue_name:
        return False
    venue = session.execute(
        select(PublicationVenue).where(
            PublicationVenue.source == SOURCE, PublicationVenue.source_venue_id == venue_name
        )
    ).scalar_one_or_none()
    if venue is None:
        venue = PublicationVenue(source=SOURCE, source_venue_id=venue_name, name=venue_name, venue_type="unknown")
        session.add(venue)
        session.flush()
    link_exists = session.execute(
        select(PaperVenue).where(PaperVenue.paper_id == paper_id, PaperVenue.venue_id == venue.id)
    ).scalar_one_or_none()
    if link_exists is None:
        session.add(PaperVenue(paper_id=paper_id, venue_id=venue.id, publication_date=None))
        return True
    return False


def _store_enrichment_result(session, paper: Paper, result: dict) -> dict:
    """Pure DB-write phase -- no network/pacing calls inside it, matching
    the arXiv/OpenAlex-derived lesson about SAVEPOINT + session.commit()
    interaction. Never writes to any canonical `papers` field (title,
    abstract, author order, dates, categories, or doi) -- everything here
    is additive and source-tagged, so OpenAlex and Semantic Scholar values
    can never silently overwrite each other or arXiv's own data."""
    _upsert_match_record(session, paper.id, result)

    stats = {
        "arxiv_id": paper.arxiv_id,
        "match_status": result["match_status"],
        "match_method": result["match_method"],
        "s2_paper_id": result["matched_external_id"],
        "references_stored": 0,
        "citation_snapshot_stored": False,
        "venue_added": False,
        "authors_matched": 0,
        "authors_skipped": 0,
        "institutions_captured": 0,
    }

    if result["match_status"] == "MATCHED":
        s2_paper = result["matched_paper"]
        _upsert_source_record(session, paper.id, s2_paper)
        stats["citation_snapshot_stored"] = _record_citation_snapshot(session, paper.id, s2_paper)
        stats["references_stored"] = _store_references(session, paper.id, s2_paper)
        stats["venue_added"] = _enrich_venue(session, paper.id, s2_paper)
        stats.update(_enrich_authors_and_institutions(session, paper.id, s2_paper))

    return stats


def run_semantic_scholar_enrichment(paper_ids: list) -> dict:
    """Enriches existing canonical papers only -- never creates a new
    papers row. Matching (network) happens outside any SAVEPOINT; only DB
    writes are wrapped in one, per paper, so one failure never affects
    another paper's already-committed work."""
    session = SessionLocal()
    try:
        config_snapshot = {"paper_count": len(paper_ids)}
        per_paper_results = []
        with IngestionRunTracker(
            session, job_type="semantic_scholar_enrichment", config_snapshot=config_snapshot
        ) as tracker:
            for paper_id in paper_ids:
                tracker.record_processed()
                paper = session.get(Paper, paper_id)
                try:
                    author_names = _get_author_names(session, paper)
                    publication_year = _get_publication_year(session, paper)
                    known_s2_id = _known_s2_id(session, paper.id)
                    result = match_paper(session, paper, author_names, publication_year, known_s2_id)

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
