from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Matches the exact JSON shape every registered exception handler in
    exceptions.py already returns ({"detail": str(exc)}) -- this schema
    documents existing behavior, it does not change it."""

    detail: str
