from fastapi import APIRouter, Query

from research_platform.api.schemas.clusters import (
    ClusterDetail,
    ClusterListResponse,
    ClusterPapersResponse,
    NoisePapersResponse,
)
from research_platform.api.schemas.errors import ErrorResponse
from research_platform.clustering.queries import (
    get_cluster_detail,
    get_cluster_papers,
    get_noise_papers,
    list_approved_clusters,
)

router = APIRouter(prefix="/clusters", tags=["clusters"])


# Registered BEFORE /{cluster_id}: Starlette matches routes in declaration
# order, and /{cluster_id} would otherwise capture the literal path
# "/clusters/noise" first, failing int conversion and never falling
# through to this route.
@router.get("/noise", response_model=NoisePapersResponse)
def noise_papers(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category: str | None = Query(None),
) -> NoisePapersResponse:
    result = get_noise_papers(limit=limit, offset=offset, category=category)
    return NoisePapersResponse(**result)


@router.get("", response_model=ClusterListResponse)
def list_clusters() -> ClusterListResponse:
    result = list_approved_clusters()
    return ClusterListResponse(**result)


@router.get(
    "/{cluster_id}",
    response_model=ClusterDetail,
    responses={404: {"description": "Cluster not found or approved label unavailable", "model": ErrorResponse}},
)
def cluster_detail(cluster_id: int) -> ClusterDetail:
    result = get_cluster_detail(cluster_id)
    return ClusterDetail(**result)


@router.get(
    "/{cluster_id}/papers",
    response_model=ClusterPapersResponse,
    responses={404: {"description": "Cluster not found or approved label unavailable", "model": ErrorResponse}},
)
def cluster_papers(
    cluster_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category: str | None = Query(None),
    min_membership_probability: float | None = Query(None, ge=0, le=1),
) -> ClusterPapersResponse:
    result = get_cluster_papers(
        cluster_id,
        limit=limit,
        offset=offset,
        category=category,
        min_membership_probability=min_membership_probability,
    )
    return ClusterPapersResponse(**result)
