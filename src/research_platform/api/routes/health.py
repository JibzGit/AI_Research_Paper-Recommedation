from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from research_platform.api.dependencies import check_database_connected
from research_platform.api.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    responses={
        200: {"description": "API is running and the database is reachable", "model": HealthResponse},
        503: {"description": "API is running but the database is unreachable", "model": HealthResponse},
    },
)
def health() -> JSONResponse:
    if check_database_connected():
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "healthy", "database": "connected"},
        )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "unhealthy", "database": "disconnected"},
    )
