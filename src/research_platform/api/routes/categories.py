from fastapi import APIRouter

from research_platform.api.schemas.categories import CategoryListResponse
from research_platform.papers.queries import list_categories

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=CategoryListResponse)
def categories() -> CategoryListResponse:
    items = list_categories()
    return CategoryListResponse(count=len(items), categories=items)
