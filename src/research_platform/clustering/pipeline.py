import importlib.metadata
import uuid
from collections import Counter
from datetime import datetime, timezone

import hdbscan
import numpy as np
import umap
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from research_platform import config
from research_platform.db.models import Category, ClusteringRun, Paper, PaperClusterAssignment, PaperEmbedding
from research_platform.db.session import SessionLocal

# Fixed per the approved design -- random_seed is the one parameter exposed
# as an argument (default 42) since it's what determinism tests vary/pin;
# every other value is a deliberate corpus-scale decision, not meant to be
# casually overridden per call.
UMAP_PARAMS = {"n_components": 5, "n_neighbors": 15, "min_dist": 0.0, "metric": "cosine"}
HDBSCAN_PARAMS = {
    "min_cluster_size": 5,
    "min_samples": 3,
    "metric": "euclidean",
    "cluster_selection_method": "eom",
    "prediction_data": True,
}


def _library_versions() -> dict:
    return {
        "umap-learn": importlib.metadata.version("umap-learn"),
        "hdbscan": importlib.metadata.version("hdbscan"),
    }


def _select_eligible_embeddings(session) -> tuple[list, np.ndarray]:
    """Same eligibility filter as search_papers()/similar_papers():
    SUCCEEDED, current configured (model, version), canonical papers only.
    Ordered by paper_id for a stable, reproducible input order -- UMAP's
    approximate nearest-neighbor step can be sensitive to input ordering,
    so this matters for the "deterministic reruns" guarantee, not just
    tidiness."""
    rows = session.execute(
        select(PaperEmbedding.paper_id, PaperEmbedding.embedding)
        .join(Paper, Paper.id == PaperEmbedding.paper_id)
        .where(
            PaperEmbedding.embedding_status == "SUCCEEDED",
            PaperEmbedding.embedding_model == config.EMBEDDING_MODEL_NAME,
            PaperEmbedding.model_version == config.EMBEDDING_MODEL_REVISION,
            Paper.is_canonical.is_(True),
        )
        .order_by(PaperEmbedding.paper_id)
    ).all()
    paper_ids = [row.paper_id for row in rows]
    vectors = np.array([row.embedding for row in rows], dtype=np.float64)
    return paper_ids, vectors


def run_clustering(random_seed: int = 42) -> dict:
    """Runs UMAP -> HDBSCAN once over every eligible paper's embedding and
    stores one assignment row per paper. Never modifies `papers` or
    `paper_embeddings` -- only ever writes to clustering_runs and
    paper_cluster_assignments.

    Unlike the per-paper embedding job, failure isolation here is at the
    level of the WHOLE RUN, not per paper: UMAP/HDBSCAN operate on the
    entire matrix jointly (there's no such thing as "cluster one paper at
    a time"), so a run either produces a complete, consistent set of
    assignments or none at all -- a mid-run exception rolls back any
    assignment inserts already staged in this session and marks the run
    FAILED, rather than leaving a partial/inconsistent clustering on disk.
    """
    config.validate_embedding_config()
    session = SessionLocal()
    try:
        paper_ids, vectors = _select_eligible_embeddings(session)
        paper_count = len(paper_ids)

        algorithm_parameters = {
            "umap": {**UMAP_PARAMS, "random_state": random_seed},
            "hdbscan": dict(HDBSCAN_PARAMS),
            "library_versions": _library_versions(),
        }

        run = ClusteringRun(
            embedding_model=config.EMBEDDING_MODEL_NAME,
            embedding_model_version=config.EMBEDDING_MODEL_REVISION,
            algorithm_parameters=algorithm_parameters,
            random_seed=random_seed,
            paper_count=paper_count,
            cluster_count=0,
            noise_count=0,
            status="RUNNING",
            created_at=datetime.now(timezone.utc),
        )
        session.add(run)
        session.commit()

        try:
            cluster_count = 0
            noise_count = 0
            cluster_persistence: list[float] = []

            if paper_count > 0:
                reducer = umap.UMAP(**UMAP_PARAMS, random_state=random_seed)
                reduced = reducer.fit_transform(vectors)

                if not np.isfinite(reduced).all():
                    raise ValueError("UMAP produced non-finite coordinates (NaN/Inf) -- refusing to store")

                clusterer = hdbscan.HDBSCAN(**HDBSCAN_PARAMS)
                labels = clusterer.fit_predict(reduced)
                probabilities = clusterer.probabilities_

                cluster_count = int(len(set(labels) - {-1}))
                noise_count = int((labels == -1).sum())
                cluster_persistence = [float(p) for p in clusterer.cluster_persistence_]

                now = datetime.now(timezone.utc)
                for paper_id, label, probability, coords in zip(paper_ids, labels, probabilities, reduced):
                    is_noise = bool(label == -1)
                    session.execute(
                        pg_insert(PaperClusterAssignment).values(
                            clustering_run_id=run.id,
                            paper_id=paper_id,
                            cluster_id=None if is_noise else int(label),
                            membership_probability=float(probability),
                            is_noise=is_noise,
                            umap_coordinates=[float(x) for x in coords],
                            created_at=now,
                        )
                    )
                session.commit()

            run.cluster_count = cluster_count
            run.noise_count = noise_count
            run.status = "SUCCEEDED"
            run.completed_at = datetime.now(timezone.utc)
            session.add(run)
            session.commit()

        except Exception:
            session.rollback()
            run.status = "FAILED"
            run.completed_at = datetime.now(timezone.utc)
            session.add(run)
            session.commit()
            raise

        return {
            "run_id": str(run.id),
            "status": run.status,
            "paper_count": paper_count,
            "cluster_count": run.cluster_count,
            "noise_count": run.noise_count,
            "cluster_persistence": cluster_persistence,
        }
    finally:
        session.close()


def describe_run(run_id: str, top_n_representative: int = 3, top_n_keywords: int = 8) -> dict:
    """Read-only report builder for an existing run: per-cluster size,
    average membership probability, representative papers (nearest the
    cluster centroid in UMAP space), category distribution, and simple
    top-keyword extraction from member titles/abstracts. Never touches
    papers/paper_embeddings; only reads clustering tables + papers/
    categories for display."""
    session = SessionLocal()
    try:
        run = session.get(ClusteringRun, uuid.UUID(str(run_id)))
        if run is None:
            raise ValueError(f"clustering run not found: {run_id}")

        assignments = session.execute(
            select(
                PaperClusterAssignment.paper_id,
                PaperClusterAssignment.cluster_id,
                PaperClusterAssignment.membership_probability,
                PaperClusterAssignment.is_noise,
                PaperClusterAssignment.umap_coordinates,
                Paper.arxiv_id,
                Paper.title,
                Paper.abstract,
                Category.code,
                Category.display_name,
            )
            .join(Paper, Paper.id == PaperClusterAssignment.paper_id)
            .join(Category, Category.id == Paper.primary_category_id)
            .where(PaperClusterAssignment.clustering_run_id == run.id)
        ).all()

        by_cluster: dict[int, list] = {}
        for a in assignments:
            if a.is_noise:
                continue
            by_cluster.setdefault(a.cluster_id, []).append(a)

        stopwords = {
            "the", "a", "an", "of", "and", "to", "in", "for", "on", "with", "is", "are",
            "we", "this", "that", "by", "as", "our", "be", "can", "using", "from", "an",
            "these", "which", "it", "its", "at", "or", "such", "based", "propose", "paper",
        }

        clusters_report = []
        for cluster_id in sorted(by_cluster):
            members = by_cluster[cluster_id]
            size = len(members)
            avg_prob = sum(m.membership_probability for m in members) / size

            coords = np.array([m.umap_coordinates for m in members])
            centroid = coords.mean(axis=0)
            distances = np.linalg.norm(coords - centroid, axis=1)
            order = np.argsort(distances)
            representative = [
                {"arxiv_id": members[i].arxiv_id, "title": members[i].title}
                for i in order[:top_n_representative]
            ]

            category_counts = Counter((m.display_name or m.code) for m in members)
            category_distribution = [
                {"category": cat, "count": cnt, "percent": round(100 * cnt / size, 1)}
                for cat, cnt in category_counts.most_common()
            ]

            word_counts = Counter()
            for m in members:
                text = f"{m.title} {m.abstract}".lower()
                for word in text.replace(",", " ").replace(".", " ").replace(":", " ").split():
                    word = word.strip("()[]{}\"'")
                    if len(word) > 2 and word not in stopwords:
                        word_counts[word] += 1
            top_keywords = [w for w, _ in word_counts.most_common(top_n_keywords)]

            clusters_report.append(
                {
                    "cluster_id": cluster_id,
                    "size": size,
                    "average_membership_probability": round(avg_prob, 4),
                    "top_keywords": top_keywords,
                    "representative_papers": representative,
                    "category_distribution": category_distribution,
                }
            )

        noise_count = sum(1 for a in assignments if a.is_noise)
        return {
            "run_id": str(run.id),
            "paper_count": run.paper_count,
            "cluster_count": run.cluster_count,
            "noise_count": noise_count,
            "noise_percent": round(100 * noise_count / run.paper_count, 1) if run.paper_count else 0.0,
            "clusters": clusters_report,
        }
    finally:
        session.close()
