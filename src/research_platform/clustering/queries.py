import numpy as np
from sqlalchemy import func, select

from research_platform.db.models import Category, ClusterLabel, ClusteringRun, Paper, PaperClusterAssignment
from research_platform.db.session import SessionLocal
from research_platform.embeddings.search import fetch_authors_batched, publication_date_subquery


class ClusterNotFoundError(ValueError):
    """Raised only when no APPROVED label exists for the given cluster_id
    under the latest SUCCEEDED run -- covers all three "doesn't exist"
    cases at once: the cluster_id never existed, it exists but has no
    approved label, or it belonged to an older (non-latest) run."""


def get_latest_successful_run(session) -> ClusteringRun | None:
    return session.execute(
        select(ClusteringRun)
        .where(ClusteringRun.status == "SUCCEEDED")
        .order_by(ClusteringRun.completed_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _dominant_categories(session, run_id, cluster_ids: list[int]) -> dict[int, str]:
    if not cluster_ids:
        return {}
    rows = session.execute(
        select(
            PaperClusterAssignment.cluster_id,
            Category.code,
            Category.display_name,
            func.count().label("cnt"),
        )
        .join(Paper, Paper.id == PaperClusterAssignment.paper_id)
        .join(Category, Category.id == Paper.primary_category_id)
        .where(
            PaperClusterAssignment.clustering_run_id == run_id,
            PaperClusterAssignment.cluster_id.in_(cluster_ids),
            PaperClusterAssignment.is_noise.is_(False),
        )
        .group_by(PaperClusterAssignment.cluster_id, Category.code, Category.display_name)
    ).all()
    best: dict[int, tuple[int, str]] = {}
    for r in rows:
        name = r.display_name or r.code
        if r.cluster_id not in best or r.cnt > best[r.cluster_id][0]:
            best[r.cluster_id] = (r.cnt, name)
    return {cid: name for cid, (_, name) in best.items()}


def _category_distribution(session, run_id, cluster_id: int, total: int) -> list[dict]:
    rows = session.execute(
        select(Category.code, Category.display_name, func.count().label("cnt"))
        .select_from(PaperClusterAssignment)
        .join(Paper, Paper.id == PaperClusterAssignment.paper_id)
        .join(Category, Category.id == Paper.primary_category_id)
        .where(
            PaperClusterAssignment.clustering_run_id == run_id,
            PaperClusterAssignment.cluster_id == cluster_id,
            PaperClusterAssignment.is_noise.is_(False),
        )
        .group_by(Category.code, Category.display_name)
        .order_by(func.count().desc())
    ).all()
    return [
        {"category": r.display_name or r.code, "count": r.cnt, "percent": round(100 * r.cnt / total, 1)}
        for r in rows
    ]


def _representative_papers(session, run_id, cluster_id: int, top_n: int = 3) -> list[dict]:
    """Nearest to the cluster centroid in UMAP space -- same approach as
    pipeline.describe_run(), reimplemented here rather than imported since
    describe_run() returns a full human-readable report bundling all
    clusters, not a reusable single-cluster primitive."""
    rows = session.execute(
        select(PaperClusterAssignment.paper_id, PaperClusterAssignment.umap_coordinates, Paper.arxiv_id, Paper.title)
        .join(Paper, Paper.id == PaperClusterAssignment.paper_id)
        .where(
            PaperClusterAssignment.clustering_run_id == run_id,
            PaperClusterAssignment.cluster_id == cluster_id,
            PaperClusterAssignment.is_noise.is_(False),
        )
    ).all()
    if not rows:
        return []
    coords = np.array([r.umap_coordinates for r in rows])
    centroid = coords.mean(axis=0)
    distances = np.linalg.norm(coords - centroid, axis=1)
    order = np.argsort(distances)
    return [
        {"paper_id": str(rows[i].paper_id), "arxiv_id": rows[i].arxiv_id, "title": rows[i].title}
        for i in order[:top_n]
    ]


def list_approved_clusters() -> dict:
    """Read-only. All APPROVED cluster labels under the latest SUCCEEDED
    run, sorted by paper_count descending."""
    session = SessionLocal()
    try:
        run = get_latest_successful_run(session)
        if run is None:
            return {"clustering_run_id": None, "count": 0, "clusters": []}

        agg_rows = session.execute(
            select(
                PaperClusterAssignment.cluster_id,
                func.count(PaperClusterAssignment.paper_id).label("paper_count"),
                func.avg(PaperClusterAssignment.membership_probability).label("avg_prob"),
            )
            .where(PaperClusterAssignment.clustering_run_id == run.id, PaperClusterAssignment.is_noise.is_(False))
            .group_by(PaperClusterAssignment.cluster_id)
        ).all()
        agg_by_cluster = {r.cluster_id: r for r in agg_rows}

        labels = session.execute(
            select(ClusterLabel).where(
                ClusterLabel.clustering_run_id == run.id, ClusterLabel.review_status == "APPROVED"
            )
        ).scalars().all()

        dominant_by_cluster = _dominant_categories(session, run.id, [label.cluster_id for label in labels])

        clusters = []
        for label in labels:
            agg = agg_by_cluster.get(label.cluster_id)
            clusters.append(
                {
                    "cluster_id": label.cluster_id,
                    "cluster_name": label.cluster_name,
                    "short_description": label.short_description,
                    "paper_count": agg.paper_count if agg else 0,
                    "label_confidence": label.confidence,
                    "top_keywords": label.keywords or [],
                    "dominant_category": dominant_by_cluster.get(label.cluster_id),
                    "average_membership_probability": float(agg.avg_prob) if agg else 0.0,
                    "clustering_run_id": str(run.id),
                }
            )
        clusters.sort(key=lambda c: c["paper_count"], reverse=True)
        return {"clustering_run_id": str(run.id), "count": len(clusters), "clusters": clusters}
    finally:
        session.close()


def get_cluster_detail(cluster_id: int) -> dict:
    """Read-only. Raises ClusterNotFoundError if the cluster doesn't exist,
    has no APPROVED label, or isn't part of the latest SUCCEEDED run."""
    session = SessionLocal()
    try:
        run = get_latest_successful_run(session)
        if run is None:
            raise ClusterNotFoundError(f"no successful clustering run available; cluster {cluster_id} not found")

        label = session.execute(
            select(ClusterLabel).where(
                ClusterLabel.clustering_run_id == run.id,
                ClusterLabel.cluster_id == cluster_id,
                ClusterLabel.review_status == "APPROVED",
            )
        ).scalar_one_or_none()
        if label is None:
            raise ClusterNotFoundError(
                f"no approved cluster label for cluster_id={cluster_id} in the latest run ({run.id})"
            )

        agg = session.execute(
            select(
                func.count(PaperClusterAssignment.paper_id).label("paper_count"),
                func.avg(PaperClusterAssignment.membership_probability).label("avg_prob"),
            ).where(
                PaperClusterAssignment.clustering_run_id == run.id,
                PaperClusterAssignment.cluster_id == cluster_id,
                PaperClusterAssignment.is_noise.is_(False),
            )
        ).one()
        if not agg.paper_count:
            raise ClusterNotFoundError(f"cluster_id={cluster_id} has an approved label but no assignments")

        return {
            "cluster_id": cluster_id,
            "cluster_name": label.cluster_name,
            "short_description": label.short_description,
            "paper_count": agg.paper_count,
            "label_confidence": label.confidence,
            "keywords": label.keywords or [],
            "evidence": label.evidence or [],
            "category_distribution": _category_distribution(session, run.id, cluster_id, agg.paper_count),
            "average_membership_probability": float(agg.avg_prob),
            "representative_papers": _representative_papers(session, run.id, cluster_id),
            "clustering_run_id": str(run.id),
            "created_at": label.created_at,
            "reviewed_by": label.reviewed_by,
            "reviewed_at": label.reviewed_at,
        }
    finally:
        session.close()


def _paginated_papers(
    session, run_id, *, cluster_id: int | None, is_noise: bool | None,
    limit: int, offset: int, category: str | None, min_membership_probability: float | None,
) -> tuple[int, list[dict]]:
    """Shared pagination/filter/formatting core for both cluster-papers and
    noise-papers endpoints -- the only difference between them is which
    PaperClusterAssignment rows are selected (by cluster_id vs is_noise)."""
    v1_versions, publication_date_expr = publication_date_subquery()

    stmt = (
        select(
            Paper.id.label("paper_id"),
            Paper.arxiv_id,
            Paper.title,
            Paper.abstract,
            Category.code.label("category_code"),
            Category.display_name.label("category_display_name"),
            publication_date_expr.label("publication_date"),
            PaperClusterAssignment.membership_probability,
            PaperClusterAssignment.is_noise,
        )
        .select_from(PaperClusterAssignment)
        .join(Paper, Paper.id == PaperClusterAssignment.paper_id)
        .join(Category, Category.id == Paper.primary_category_id)
        .outerjoin(v1_versions, v1_versions.c.paper_id == Paper.id)
        .where(PaperClusterAssignment.clustering_run_id == run_id)
    )
    if cluster_id is not None:
        stmt = stmt.where(PaperClusterAssignment.cluster_id == cluster_id)
    if is_noise is not None:
        stmt = stmt.where(PaperClusterAssignment.is_noise.is_(is_noise))
    if category:
        stmt = stmt.where(Category.code == category)
    if min_membership_probability is not None:
        stmt = stmt.where(PaperClusterAssignment.membership_probability >= min_membership_probability)

    total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    stmt = stmt.order_by(PaperClusterAssignment.membership_probability.desc(), Paper.arxiv_id.asc())
    stmt = stmt.limit(limit).offset(offset)
    rows = session.execute(stmt).all()

    paper_ids = [row.paper_id for row in rows]
    authors_by_paper = fetch_authors_batched(session, paper_ids)

    papers = [
        {
            "paper_id": str(row.paper_id),
            "arxiv_id": row.arxiv_id,
            "title": row.title,
            "abstract": row.abstract,
            "authors": authors_by_paper.get(row.paper_id, []),
            "primary_category": row.category_display_name or row.category_code,
            "publication_date": row.publication_date,
            "membership_probability": float(row.membership_probability),
            "is_noise": row.is_noise,
        }
        for row in rows
    ]
    return total, papers


def get_cluster_papers(
    cluster_id: int, limit: int = 20, offset: int = 0,
    category: str | None = None, min_membership_probability: float | None = None,
) -> dict:
    """Read-only. Raises ClusterNotFoundError under the same rules as
    get_cluster_detail() (no silent empty-200 for a cluster that doesn't
    exist/isn't approved)."""
    session = SessionLocal()
    try:
        run = get_latest_successful_run(session)
        if run is None:
            raise ClusterNotFoundError(f"no successful clustering run available; cluster {cluster_id} not found")

        approved = session.execute(
            select(ClusterLabel.id).where(
                ClusterLabel.clustering_run_id == run.id,
                ClusterLabel.cluster_id == cluster_id,
                ClusterLabel.review_status == "APPROVED",
            )
        ).scalar_one_or_none()
        if approved is None:
            raise ClusterNotFoundError(
                f"no approved cluster label for cluster_id={cluster_id} in the latest run ({run.id})"
            )

        total, papers = _paginated_papers(
            session, run.id, cluster_id=cluster_id, is_noise=False,
            limit=limit, offset=offset, category=category, min_membership_probability=min_membership_probability,
        )
        return {"cluster_id": cluster_id, "total": total, "limit": limit, "offset": offset, "papers": papers}
    finally:
        session.close()


def get_noise_papers(limit: int = 20, offset: int = 0, category: str | None = None) -> dict:
    """Read-only. Papers marked is_noise=True in the latest SUCCEEDED run.
    No min_membership_probability filter -- noise rows are always 0.0 by
    construction (enforced at generation time and by the DB CHECK
    constraint), so the filter would be meaningless here."""
    session = SessionLocal()
    try:
        run = get_latest_successful_run(session)
        if run is None:
            return {"clustering_run_id": None, "total": 0, "limit": limit, "offset": offset, "papers": []}

        total, papers = _paginated_papers(
            session, run.id, cluster_id=None, is_noise=True,
            limit=limit, offset=offset, category=category, min_membership_probability=None,
        )
        return {"clustering_run_id": str(run.id), "total": total, "limit": limit, "offset": offset, "papers": papers}
    finally:
        session.close()
