from fastapi import APIRouter

from research_platform.api.schemas.stats import PlatformOverview
from research_platform.stats import get_platform_overview

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview", response_model=PlatformOverview)
def overview() -> PlatformOverview:
    return PlatformOverview(**get_platform_overview())
