from pydantic import BaseModel


class CategorySummary(BaseModel):
    code: str
    display_name: str
    paper_count: int


class CategoryListResponse(BaseModel):
    count: int
    categories: list[CategorySummary]
