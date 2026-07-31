from pydantic import BaseModel


class PlatformOverview(BaseModel):
    total_canonical_papers: int
    embedded_papers: int
    approved_clusters: int
    clustered_papers: int
    noise_papers: int
    latest_clustering_run_id: str | None
    database_status: str
