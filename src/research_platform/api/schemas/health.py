from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Shared shape for both outcomes of GET /health -- only the values of
    status/database differ ("healthy"/"connected" vs "unhealthy"/
    "disconnected"), documented here for both the 200 and 503 responses
    rather than leaving 200 undocumented while only 503 has a real schema."""

    status: str
    database: str
