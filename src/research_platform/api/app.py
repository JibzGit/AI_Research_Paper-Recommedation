from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from research_platform import config
from research_platform.api.exceptions import register_exception_handlers
from research_platform.api.routes import categories, clusters, health, papers, stats, trends

app = FastAPI(title="Research Platform API", version="0.1.0")

# allow_credentials is hardcoded False: this API has no cookies/auth, and
# keeping it False means CORS_ALLOWED_ORIGINS could never be misconfigured
# into an unsafe wildcard-plus-credentials combination.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(papers.router, prefix="/api/v1")
app.include_router(clusters.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")
app.include_router(categories.router, prefix="/api/v1")
app.include_router(trends.router, prefix="/api/v1")

register_exception_handlers(app)
