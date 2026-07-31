from sqlalchemy import func, select

from research_platform import config
from research_platform.clustering.queries import get_latest_successful_run
from research_platform.db.models import ClusterLabel, Paper, PaperClusterAssignment, PaperEmbedding
from research_platform.db.session import SessionLocal


def get_platform_overview() -> dict:
    """Read-only aggregate counts for the frontend dashboard. Every value is
    computed here, never hardcoded. total_canonical_papers/embedded_papers
    reflect the whole corpus regardless of clustering state; approved_
    clusters/clustered_papers/noise_papers/latest_clustering_run_id are
    scoped to the latest SUCCEEDED clustering run and zero/null out safely
    when none exists (same "no run" outcome clustering.queries functions
    already handle, applied consistently here).

    database_status is always "connected" whenever this function returns at
    all: reaching the return statement already required the count queries
    below to execute successfully against the database, so a genuine outage
    would raise (and surface as the generic 500 handler) rather than ever
    letting this function report "disconnected" in a 200 response."""
    session = SessionLocal()
    try:
        total_canonical_papers = session.execute(
            select(func.count()).select_from(Paper).where(Paper.is_canonical.is_(True))
        ).scalar_one()

        embedded_papers = session.execute(
            select(func.count(func.distinct(PaperEmbedding.paper_id)))
            .select_from(PaperEmbedding)
            .join(Paper, Paper.id == PaperEmbedding.paper_id)
            .where(
                PaperEmbedding.embedding_status == "SUCCEEDED",
                PaperEmbedding.embedding_model == config.EMBEDDING_MODEL_NAME,
                PaperEmbedding.model_version == config.EMBEDDING_MODEL_REVISION,
                Paper.is_canonical.is_(True),
            )
        ).scalar_one()

        run = get_latest_successful_run(session)
        if run is None:
            return {
                "total_canonical_papers": total_canonical_papers,
                "embedded_papers": embedded_papers,
                "approved_clusters": 0,
                "clustered_papers": 0,
                "noise_papers": 0,
                "latest_clustering_run_id": None,
                "database_status": "connected",
            }

        approved_clusters = session.execute(
            select(func.count()).select_from(ClusterLabel).where(
                ClusterLabel.clustering_run_id == run.id,
                ClusterLabel.review_status == "APPROVED",
            )
        ).scalar_one()

        clustered_papers = session.execute(
            select(func.count()).select_from(PaperClusterAssignment).where(
                PaperClusterAssignment.clustering_run_id == run.id,
                PaperClusterAssignment.is_noise.is_(False),
            )
        ).scalar_one()

        noise_papers = session.execute(
            select(func.count()).select_from(PaperClusterAssignment).where(
                PaperClusterAssignment.clustering_run_id == run.id,
                PaperClusterAssignment.is_noise.is_(True),
            )
        ).scalar_one()

        return {
            "total_canonical_papers": total_canonical_papers,
            "embedded_papers": embedded_papers,
            "approved_clusters": approved_clusters,
            "clustered_papers": clustered_papers,
            "noise_papers": noise_papers,
            "latest_clustering_run_id": str(run.id),
            "database_status": "connected",
        }
    finally:
        session.close()
