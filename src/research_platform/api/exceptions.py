import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from research_platform.clustering.queries import ClusterNotFoundError
from research_platform.embeddings.recommend import PaperNotFoundError
from research_platform.trends.api_queries import (
    TrendEntityNotFoundError,
    TrendResultsUnavailableError,
    TrendRunNotFoundError,
)

logger = logging.getLogger(__name__)


async def paper_not_found_handler(request: Request, exc: PaperNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


async def cluster_not_found_handler(request: Request, exc: ClusterNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


async def trend_run_not_found_handler(request: Request, exc: TrendRunNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


async def trend_entity_not_found_handler(request: Request, exc: TrendEntityNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


async def trend_results_unavailable_handler(request: Request, exc: TrendResultsUnavailableError) -> JSONResponse:
    """503, not 404: a successful trend run has never completed yet -- the
    resource isn't missing, the feature isn't ready. Same distinction
    /health already draws between "unreachable" (503) and "not found"."""
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": str(exc)})


async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Registered for the base ValueError -- Starlette dispatches to the
    most specific registered handler by exact type first, so a
    PaperNotFoundError/ClusterNotFoundError (both ValueError subclasses)
    are caught by their own handlers above, not this one. No message
    string-matching anywhere: the type is what decides the status code."""
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)})


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Never leaks internals (stack trace, exception type, message) to the
    client -- same posture as never exposing API keys elsewhere in this
    project. Full detail goes to the server log only."""
    logger.exception("unhandled error handling %s", request.url.path)
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": "internal server error"})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(PaperNotFoundError, paper_not_found_handler)
    app.add_exception_handler(ClusterNotFoundError, cluster_not_found_handler)
    app.add_exception_handler(TrendRunNotFoundError, trend_run_not_found_handler)
    app.add_exception_handler(TrendEntityNotFoundError, trend_entity_not_found_handler)
    app.add_exception_handler(TrendResultsUnavailableError, trend_results_unavailable_handler)
    app.add_exception_handler(ValueError, value_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
