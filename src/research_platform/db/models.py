import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from research_platform.db.base import Base


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def created_at_col() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


def updated_at_col() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


# --- Taxonomy -----------------------------------------------------------

class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = uuid_pk()
    taxonomy_source: Mapped[str] = mapped_column(Text, nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        UniqueConstraint("taxonomy_source", "code", name="uq_categories_source_code"),
    )


# --- Canonical paper ------------------------------------------------------

class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[uuid.UUID] = uuid_pk()
    arxiv_id: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    doi: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    normalized_title: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str] = mapped_column(Text, nullable=False)
    primary_category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id"), nullable=False)
    first_observed_source: Mapped[str] = mapped_column(Text, nullable=False)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_canonical: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("papers.id"), nullable=True)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    __table_args__ = (
        Index("ix_papers_normalized_title", "normalized_title"),
        Index("ix_papers_first_observed_at", "first_observed_at"),
        Index("ix_papers_primary_category_id", "primary_category_id"),
    )


class PaperSourceRecord(Base):
    __tablename__ = "paper_source_records"

    id: Mapped[uuid.UUID] = uuid_pk()
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id"), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_paper_id: Mapped[str] = mapped_column(Text, nullable=False)
    raw_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    __table_args__ = (
        UniqueConstraint("paper_id", "source", name="uq_paper_source_records_paper_source"),
        UniqueConstraint("source", "source_paper_id", name="uq_paper_source_records_source_id"),
        Index("ix_paper_source_records_paper_id", "paper_id"),
    )


class PaperVersion(Base):
    __tablename__ = "paper_versions"

    id: Mapped[uuid.UUID] = uuid_pk()
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id"), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    version_identifier: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        UniqueConstraint("paper_id", "version_number", name="uq_paper_versions_paper_version"),
        Index(
            "uq_paper_versions_one_latest_per_paper",
            "paper_id",
            unique=True,
            postgresql_where=text("is_latest = true"),
        ),
        Index("ix_paper_versions_paper_id", "paper_id"),
    )


# --- Authors and institutions --------------------------------------------

class Author(Base):
    __tablename__ = "authors"

    id: Mapped[uuid.UUID] = uuid_pk()
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_author_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_name: Mapped[str] = mapped_column(Text, nullable=False)
    identity_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'UNRESOLVED'"))
    identity_confidence: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    __table_args__ = (
        Index(
            "uq_authors_source_author_id",
            "source",
            "source_author_id",
            unique=True,
            postgresql_where=text("source IS NOT NULL AND source_author_id IS NOT NULL"),
        ),
        Index("ix_authors_normalized_name", "normalized_name"),
    )


class PaperAuthor(Base):
    __tablename__ = "paper_authors"

    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id"), primary_key=True)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("authors.id"), primary_key=True)
    author_order: Mapped[int] = mapped_column(Integer, nullable=False)
    affiliation_text_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        UniqueConstraint("paper_id", "author_order", name="uq_paper_authors_paper_order"),
        Index("ix_paper_authors_author_id", "author_id"),
    )


class Institution(Base):
    __tablename__ = "institutions"

    id: Mapped[uuid.UUID] = uuid_pk()
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_institution_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    country_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    __table_args__ = (
        UniqueConstraint("source", "source_institution_id", name="uq_institutions_source_id"),
    )


class PaperAuthorInstitution(Base):
    __tablename__ = "paper_author_institutions"

    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id"), primary_key=True)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("authors.id"), primary_key=True)
    institution_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("institutions.id"), primary_key=True)
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        Index("ix_paper_author_institutions_paper_id", "paper_id"),
    )


# --- Categories and venues (paper-linked) ---------------------------------

class PaperCategory(Base):
    __tablename__ = "paper_categories"

    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id"), primary_key=True)
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id"), primary_key=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        Index(
            "uq_paper_categories_one_primary_per_paper",
            "paper_id",
            unique=True,
            postgresql_where=text("is_primary = true"),
        ),
        Index("ix_paper_categories_category_id", "category_id"),
    )


class PublicationVenue(Base):
    __tablename__ = "publication_venues"

    id: Mapped[uuid.UUID] = uuid_pk()
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_venue_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    venue_type: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    __table_args__ = (
        Index(
            "uq_publication_venues_source_id",
            "source",
            "source_venue_id",
            unique=True,
            postgresql_where=text("source IS NOT NULL AND source_venue_id IS NOT NULL"),
        ),
    )


class PaperVenue(Base):
    __tablename__ = "paper_venues"

    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id"), primary_key=True)
    venue_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("publication_venues.id"), primary_key=True)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = created_at_col()


# --- Metrics (append-only) -------------------------------------------------

class PaperMetricSnapshot(Base):
    __tablename__ = "paper_metric_snapshots"

    id: Mapped[uuid.UUID] = uuid_pk()
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id"), nullable=False)
    metric_type: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[float] = mapped_column(Numeric, nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        UniqueConstraint(
            "paper_id", "metric_type", "source", "snapshot_date", name="uq_paper_metric_snapshots_key"
        ),
        Index("ix_paper_metric_snapshots_lookup", "paper_id", "metric_type", "snapshot_date"),
    )


# --- Ingestion tracking -----------------------------------------------------

class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    config_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    cursor: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    records_processed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    records_created: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    records_updated: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    records_failed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_ingestion_runs_job_status_started", "job_type", "status", "started_at"),
    )


class IngestionFailure(Base):
    __tablename__ = "ingestion_failures"

    id: Mapped[uuid.UUID] = uuid_pk()
    ingestion_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ingestion_runs.id"), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_identifier: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_type: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_ingestion_failures_run_id", "ingestion_run_id"),
        Index("ix_ingestion_failures_resolved", "resolved"),
    )


# --- Paced collection support (added for adaptive backfill + quota ingestion) --

class ApiRequestState(Base):
    """Persists shared request pacing for one external API source across
    processes and restarts. One row per source. Uses `source` as the
    primary key directly rather than a surrogate UUID: this is a small
    keyed state table (like a KV row), not an entity joined from other
    tables, so a natural key is simpler and avoids a pointless lookup.
    """

    __tablename__ = "api_request_states"

    source: Mapped[str] = mapped_column(Text, primary_key=True)
    last_request_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_allowed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    updated_at: Mapped[datetime] = updated_at_col()


class BackfillWindow(Base):
    __tablename__ = "backfill_windows"

    id: Mapped[uuid.UUID] = uuid_pk()
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_granularity: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_result_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_size: Mapped[int] = mapped_column(Integer, nullable=False)
    next_page_offset: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    records_committed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'PLANNED'"))
    split_from_window_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("backfill_windows.id"), nullable=True
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_backfill_windows_status", "status"),
        Index("ix_backfill_windows_window_start", "window_start"),
    )


class IngestionQuotaPeriod(Base):
    __tablename__ = "ingestion_quota_periods"

    id: Mapped[uuid.UUID] = uuid_pk()
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quota_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    new_papers_available: Mapped[int | None] = mapped_column(Integer, nullable=True)
    historical_papers_available: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_papers_selected: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    historical_papers_selected: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    papers_processed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    papers_failed: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    unused_capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'RUNNING'"))
    config_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_ingestion_quota_periods_status", "status"),
    )


# --- Enrichment support (OpenAlex, and later other providers) -------------

class PaperReference(Base):
    """One outbound citation edge discovered via enrichment. cited_paper_id
    is nullable because most referenced works are not (yet) canonical
    papers in this corpus -- the external identifiers are captured
    regardless, per the explicit requirement to store references without
    requiring every cited paper to already exist."""

    __tablename__ = "paper_references"

    id: Mapped[uuid.UUID] = uuid_pk()
    citing_paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id"), nullable=False)
    cited_paper_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("papers.id"), nullable=True)
    cited_external_doi: Mapped[str | None] = mapped_column(Text, nullable=True)
    cited_external_openalex_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    cited_external_arxiv_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index(
            "uq_paper_references_citing_source_openalex_id",
            "citing_paper_id",
            "source",
            "cited_external_openalex_id",
            unique=True,
            postgresql_where=text("cited_external_openalex_id IS NOT NULL"),
        ),
        Index("ix_paper_references_citing_paper_id", "citing_paper_id"),
        Index("ix_paper_references_cited_paper_id", "cited_paper_id"),
    )


class PaperEnrichmentMatch(Base):
    """Records the outcome of every enrichment match attempt for a
    (paper, source) pair -- including AMBIGUOUS/NOT_FOUND/FAILED, which
    paper_source_records cannot represent since it only exists for
    successful links. Upserted by (paper_id, source) so reruns update the
    same row rather than duplicating -- this is what makes enrichment
    reruns idempotent."""

    __tablename__ = "paper_enrichment_matches"

    id: Mapped[uuid.UUID] = uuid_pk()
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id"), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    match_status: Mapped[str] = mapped_column(Text, nullable=False)
    match_method: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    matched_external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    matching_rule_version: Mapped[str] = mapped_column(Text, nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = updated_at_col()

    __table_args__ = (
        UniqueConstraint("paper_id", "source", name="uq_paper_enrichment_matches_paper_source"),
        Index("ix_paper_enrichment_matches_status", "match_status"),
    )


# --- Source-record identity audit trail ------------------------------------

class PaperSourceRecordIdentifierHistory(Base):
    """Append-only log of every time a provider returned a different
    source_paper_id for a (paper_id, source) that already had a source
    record. Exists specifically so an external ID change (e.g. a provider
    merging/redirecting a duplicate record on their side) never silently
    loses the old identifier -- the old and new IDs are both preserved
    here even though paper_source_records itself only keeps the current one."""

    __tablename__ = "paper_source_record_identifier_history"

    id: Mapped[uuid.UUID] = uuid_pk()
    paper_source_record_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("paper_source_records.id"), nullable=False)
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id"), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    old_source_paper_id: Mapped[str] = mapped_column(Text, nullable=False)
    new_source_paper_id: Mapped[str] = mapped_column(Text, nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_paper_source_record_identifier_history_record_id", "paper_source_record_id"),
        Index("ix_paper_source_record_identifier_history_paper_source", "paper_id", "source"),
    )


# --- Source-generic enrichment queue ---------------------------------------

class EnrichmentQueue(Base):
    """One evolving row per (paper_id, source) representing the current
    queue state for that pair -- not a history of every queue event. A
    paper qualifying for a new reason updates the existing row (priority
    raised if appropriate, reason appended to contributing_reasons) rather
    than creating a second active job, per the one-active-item-per-pair
    requirement."""

    __tablename__ = "enrichment_queue"

    id: Mapped[uuid.UUID] = uuid_pk()
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id"), nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    contributing_reasons: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'[]'"))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'PENDING'"))
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    last_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_fields: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'identity_only'"))
    rule_version: Mapped[str] = mapped_column(Text, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    __table_args__ = (
        UniqueConstraint("paper_id", "source", name="uq_enrichment_queue_paper_source"),
        Index("ix_enrichment_queue_status_priority", "status", "priority"),
        Index("ix_enrichment_queue_next_retry_at", "next_retry_at"),
    )


# --- Embeddings -------------------------------------------------------------

class PaperEmbedding(Base):
    """One row per (paper, embedding_model, model_version). A model_version
    bump inserts a new row rather than overwriting the prior version's row
    in place, so multiple versions of a model's output can coexist during a
    migration to a newer version. embedding is nullable so PENDING/FAILED
    rows can exist before generation succeeds; the check constraint below
    enforces that a SUCCEEDED row always has a vector, at the DB level."""

    __tablename__ = "paper_embeddings"

    id: Mapped[uuid.UUID] = uuid_pk()
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id"), nullable=False)
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    source_text_hash: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'PENDING'"))
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    __table_args__ = (
        UniqueConstraint(
            "paper_id", "embedding_model", "model_version",
            name="uq_paper_embeddings_paper_model_version",
        ),
        CheckConstraint(
            "embedding_status <> 'SUCCEEDED' OR embedding IS NOT NULL",
            name="ck_paper_embeddings_succeeded_has_vector",
        ),
        Index("ix_paper_embeddings_status", "embedding_status"),
    )


# --- Clustering ---------------------------------------------------------

class ClusteringRun(Base):
    """One row per pipeline execution. Append-only: a rerun always creates
    a new row rather than overwriting a prior run, so cluster history is
    never lost and every run is independently reproducible/traceable back
    to the exact embedding model/version and algorithm parameters (incl.
    library versions, since umap-learn/hdbscan behavior can shift across
    versions even with identical parameters) it used."""

    __tablename__ = "clustering_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    embedding_model: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_model_version: Mapped[str] = mapped_column(Text, nullable=False)
    algorithm_parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    random_seed: Mapped[int] = mapped_column(Integer, nullable=False)
    paper_count: Mapped[int] = mapped_column(Integer, nullable=False)
    cluster_count: Mapped[int] = mapped_column(Integer, nullable=False)
    noise_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'RUNNING'"))
    created_at: Mapped[datetime] = created_at_col()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PaperClusterAssignment(Base):
    """One row per (clustering_run_id, paper_id). umap_coordinates is a
    plain float array, not a pgvector column -- these coordinates are
    read/display-only, never queried via a pgvector similarity operator
    (no "find nearest UMAP coordinate" query is planned), so a pgvector
    VECTOR type would imply a search capability that doesn't exist here."""

    __tablename__ = "paper_cluster_assignments"

    id: Mapped[uuid.UUID] = uuid_pk()
    clustering_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clustering_runs.id"), nullable=False)
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id"), nullable=False)
    cluster_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    membership_probability: Mapped[float] = mapped_column(Float, nullable=False)
    is_noise: Mapped[bool] = mapped_column(Boolean, nullable=False)
    umap_coordinates: Mapped[list[float]] = mapped_column(ARRAY(Float), nullable=False)
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        UniqueConstraint("clustering_run_id", "paper_id", name="uq_paper_cluster_assignments_run_paper"),
        CheckConstraint(
            "membership_probability >= 0 AND membership_probability <= 1",
            name="ck_paper_cluster_assignments_probability_range",
        ),
        CheckConstraint(
            "NOT is_noise OR cluster_id IS NULL",
            name="ck_paper_cluster_assignments_noise_has_null_cluster",
        ),
        CheckConstraint(
            "is_noise OR cluster_id IS NOT NULL",
            name="ck_paper_cluster_assignments_non_noise_has_cluster",
        ),
        Index("ix_paper_cluster_assignments_run_cluster", "clustering_run_id", "cluster_id"),
    )


class ClusterLabel(Base):
    """One row per (clustering_run, cluster, provider, model, model_version,
    prompt_version) -- upserted on that identity, the same pattern as
    PaperEmbedding's (paper_id, embedding_model, model_version): a
    regenerated label (changed input_hash) updates the existing row rather
    than duplicating. model_version is NOT NULL (unlike a hypothetical
    optional field) specifically to avoid Postgres unique-constraint
    semantics where NULL != NULL would silently allow duplicate slots --
    for Anthropic, the model identifier string itself is already
    version-bearing (e.g. "claude-haiku-4-5-20251001"), so model_version is
    simply set equal to model.

    LLM-generated content only becomes the "official" cluster label once
    review_status='APPROVED' by a human; until then, any future display
    layer is expected to fall back to the statistical cluster summary
    (keywords/representative papers/category distribution), which needs no
    approval since it makes no LLM-originated claims."""

    __tablename__ = "cluster_labels"

    id: Mapped[uuid.UUID] = uuid_pk()
    clustering_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clustering_runs.id"), nullable=False)
    cluster_id: Mapped[int] = mapped_column(Integer, nullable=False)
    cluster_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    input_hash: Mapped[str] = mapped_column(Text, nullable=False)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    generation_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'PENDING'"))
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    review_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'PENDING_REVIEW'"))
    reviewed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    __table_args__ = (
        UniqueConstraint(
            "clustering_run_id", "cluster_id", "provider", "model", "model_version", "prompt_version",
            name="uq_cluster_labels_identity",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_cluster_labels_confidence_range",
        ),
        CheckConstraint(
            "generation_status <> 'SUCCEEDED' OR cluster_name IS NOT NULL",
            name="ck_cluster_labels_succeeded_has_name",
        ),
        Index("ix_cluster_labels_run_cluster", "clustering_run_id", "cluster_id"),
    )


# --- Trend analysis -------------------------------------------------------

class TrendAnalysisRun(Base):
    """One row per trend-pipeline execution. Append-only, same convention
    as ClusteringRun: a rerun always creates a new row rather than
    overwriting a prior one, so trend history is never lost and every run
    stays independently reproducible via `parameters` (the exact
    thresholds/weights it used) and `calculation_version` (bumped on any
    formula/weight change in trends/scoring.py etc.). requested_trend_mode
    and effective_trend_mode are both persisted -- and can legitimately
    differ once a `current` mode exists -- because a current-mode request
    that is unavailable resolves to an explicit CURRENT_UNAVAILABLE state
    (see trends/freshness.py) rather than silently substituting a
    historical run in its place; this table only ever stores runs that
    actually executed a comparison, never a placeholder for a rejected
    current-mode request."""

    __tablename__ = "trend_analysis_runs"

    id: Mapped[uuid.UUID] = uuid_pk()
    calculation_version: Mapped[str] = mapped_column(Text, nullable=False)
    requested_trend_mode: Mapped[str] = mapped_column(Text, nullable=False)
    effective_trend_mode: Mapped[str] = mapped_column(Text, nullable=False)
    freshness_status: Mapped[str] = mapped_column(Text, nullable=False)
    corpus_latest_publication_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recent_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recent_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    comparison_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    comparison_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_granularity: Mapped[str] = mapped_column(Text, nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False)
    total_canonical_papers: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'RUNNING'"))
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at_col()
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_trend_analysis_runs_status_created", "status", "created_at"),
    )


class TrendEntitySnapshot(Base):
    """One row per (trend_run_id, entity_type, entity_id) -- the raw
    counts/windows behind a score, kept separate from TrendScore so a
    given entity's underlying comparison data stays independently
    queryable/testable from the scored outcome derived from it. entity_id
    is TEXT (not a typed FK) deliberately: it holds a cluster_id (an
    int, stored as its string form) for entity_type='cluster' and an arXiv
    category code for entity_type='category' -- a single generic column
    keeps this table entity-type-agnostic rather than needing a nullable
    FK pair. ON DELETE CASCADE on trend_run_id: unlike most FKs in this
    schema, a snapshot has no meaning independent of the run that produced
    it, so removing a run should remove its snapshots rather than leaving
    orphaned rows or requiring a separate cleanup step."""

    __tablename__ = "trend_entity_snapshots"

    id: Mapped[uuid.UUID] = uuid_pk()
    trend_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trend_analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    entity_name: Mapped[str] = mapped_column(Text, nullable=False)
    recent_paper_count: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_paper_count: Mapped[int] = mapped_column(Integer, nullable=False)
    absolute_growth: Mapped[int] = mapped_column(Integer, nullable=False)
    growth_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_new_activity: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    recent_publication_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    previous_publication_share: Mapped[float | None] = mapped_column(Float, nullable=True)
    share_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    acceleration: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    consistency: Mapped[float | None] = mapped_column(Float, nullable=True)
    recency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_papers: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        UniqueConstraint(
            "trend_run_id", "entity_type", "entity_id", name="uq_trend_entity_snapshots_run_entity"
        ),
        Index("ix_trend_entity_snapshots_run_entity", "trend_run_id", "entity_type", "entity_id"),
        Index("ix_trend_entity_snapshots_entity", "entity_type", "entity_id"),
    )


class TrendScore(Base):
    """One row per (trend_run_id, entity_type, entity_id, trend_type) --
    separate from TrendEntitySnapshot specifically so the distinct trend
    *types* (publication_trend, cluster_growth, category_growth now;
    citation_momentum/paper_momentum reserved but never inserted until a
    second metric-snapshot date exists) never collapse into one row or one
    vague "popularity" number. ON DELETE CASCADE on trend_run_id for the
    same reason as TrendEntitySnapshot -- a score has no meaning outside
    the run that produced it."""

    __tablename__ = "trend_scores"

    id: Mapped[uuid.UUID] = uuid_pk()
    trend_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trend_analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    trend_type: Mapped[str] = mapped_column(Text, nullable=False)
    trend_score: Mapped[int] = mapped_column(Integer, nullable=False)
    momentum_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    trend_classification: Mapped[str] = mapped_column(Text, nullable=False)
    data_quality_level: Mapped[str] = mapped_column(Text, nullable=False)
    component_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False)
    generated_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        UniqueConstraint(
            "trend_run_id", "entity_type", "entity_id", "trend_type",
            name="uq_trend_scores_run_entity_type",
        ),
        CheckConstraint(
            "trend_score >= 0 AND trend_score <= 100", name="ck_trend_scores_score_range"
        ),
        Index("ix_trend_scores_run_type", "trend_run_id", "trend_type"),
        Index("ix_trend_scores_classification", "trend_classification"),
    )


class TrendEvidencePaper(Base):
    """One row per (trend_score_id, paper_id, role) -- the papers backing
    a given score, mirroring ClusterLabel.evidence (a JSONB blob) but as a
    proper join table so evidence is queryable/joinable rather than opaque
    JSON. role is restricted to the two windows a paper can be evidence
    for -- there is no third role, so this is enforced with a CHECK rather
    than left as free text the way open-ended status columns elsewhere in
    this schema are. ON DELETE CASCADE on trend_score_id for the same
    reason as the other trend child tables; paper_id intentionally has no
    ondelete (consistent with every other paper_id FK in this schema --
    canonical papers are never hard-deleted, only unlinked via
    is_canonical/merged_into_id)."""

    __tablename__ = "trend_evidence_papers"

    id: Mapped[uuid.UUID] = uuid_pk()
    trend_score_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trend_scores.id", ondelete="CASCADE"), nullable=False
    )
    paper_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("papers.id"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at_col()

    __table_args__ = (
        UniqueConstraint(
            "trend_score_id", "paper_id", "role", name="uq_trend_evidence_papers_score_paper_role"
        ),
        CheckConstraint(
            "role IN ('recent_period', 'comparison_period')", name="ck_trend_evidence_papers_role"
        ),
        Index("ix_trend_evidence_papers_score", "trend_score_id"),
        Index("ix_trend_evidence_papers_paper", "paper_id"),
    )
