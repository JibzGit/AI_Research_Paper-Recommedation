# AI Research Intelligence and Paper Recommendation Platform

A research-paper platform built on a paced arXiv ingestion pipeline, BGE
embeddings + pgvector semantic search, HDBSCAN/UMAP clustering with
LLM-generated cluster labels, and Historical Cohort Comparison trend
analysis, served by a FastAPI backend and a React/Vite frontend.

## Production deployment

| Component | Platform | URL |
|---|---|---|
| Frontend (React/Vite, static) | Render Static Site (`ai-research-platform`) | https://ai-research-platform-2qyx.onrender.com |
| Backend (FastAPI) | Google Cloud Run (`ai-research-api`, project `ai-research-platform-504405`, region `us-west1`) | https://ai-research-api-vecbq5svfq-uw.a.run.app |
| Database | Neon PostgreSQL (external, pgvector extension) | not publicly exposed |

The backend was originally deployed to Render as well, but Render's free
web-service plan caps memory at 512MB, which is not enough to load the
`BAAI/bge-base-en-v1.5` embedding model (CPU-only PyTorch + the model
weights need roughly 700MB-1GB once loaded) -- it OOM-crashed repeatedly in
production. The backend now runs on Cloud Run (1 vCPU, 2GiB memory,
concurrency 1, min/max instances 0/1), with the embedding model baked into
the container image at build time (`Dockerfile.cloudrun`,
`scripts/bake_embedding_model.py`) so there's no Hugging Face Hub download
at request time. See `render.yaml` (frontend only now) and
`cloudbuild.cloudrun.yaml` / `Dockerfile.cloudrun` (backend) for the exact
deployment configuration.

The database is Neon (free tier) rather than a Render-managed Postgres
instance, because Render's own free Postgres plan auto-deletes 30 days
after creation. `DATABASE_URL` is supplied to Cloud Run via Google Secret
Manager (`neon-database-url`), never committed or baked into any image.

## Prerequisites

- Docker (with Compose v2) -- for local Postgres
- Python 3.10+
- Node.js 20+ -- for the frontend

## 1. Configure environment

```bash
cp .env.example .env
```

`.env` is git-ignored. Defaults are fine for local development. Note the
Postgres port is `5433` (not the default `5432`) to avoid colliding with any
other local Postgres instance.

## 2. Start PostgreSQL

```bash
docker compose up -d
```

Wait for the container to report healthy:

```bash
docker inspect --format='{{.State.Health.Status}}' research_platform_postgres
```

## 3. Set up the Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## 4. Run migrations

```bash
source .venv/bin/activate
alembic upgrade head
```

Migration config lives in `alembic.ini` / `migrations/env.py`, which reads
`DATABASE_URL` from `.env` via `research_platform.config`.

To inspect the applied schema directly:

```bash
docker exec research_platform_postgres psql -U research_user -d research_platform -c "\dt"
docker exec research_platform_postgres psql -U research_user -d research_platform -c "\d papers"
```

## 5. arXiv ingestion

```bash
# small controlled sample (<=25 papers, no windows/quota involved)
python3 scripts/run_sample_ingestion.py --max-results 25

# plan-only: generate adaptive backfill windows, no papers inserted
python3 scripts/plan_backfill.py --start-date 2016-01-01 --end-date 2016-04-01

# execute mode: quota-limited new+historical ingestion
python3 scripts/run_quota_ingestion.py --quota 100 --page-size 200
```

All arXiv API access is paced through `api_request_states` (shared across
processes/restarts) and protected by a Postgres advisory lock so only one
collector runs at a time. See `src/research_platform/ingestion/` for the
client, planner, and orchestrator. Embeddings (`scripts/run_embedding_backfill.py`),
clustering (`scripts/run_paper_clustering.py`), and trend analysis
(`scripts/run_trend_analysis.py`) are separate pipeline scripts, run after
ingestion.

## 6. Run the API locally

```bash
source .venv/bin/activate
uvicorn research_platform.api.app:app --reload
```

Serves on `http://127.0.0.1:8000`; interactive docs at `/docs`.

## 7. Run the frontend locally

```bash
cd frontend
npm install
cp .env.example .env   # VITE_API_BASE_URL defaults to http://127.0.0.1:8000
npm run dev
```

Serves on `http://localhost:5173`.

## 8. Stopping / resetting

```bash
docker compose down          # stop, keep data volume
docker compose down -v       # stop and delete all data (destructive)
```

## Project layout

```
docker-compose.yml          Postgres-only local service
requirements.txt            Python dependencies (full, including ingestion/clustering)
requirements-prod.txt       Strict subset used by the deployed API (excludes hdbscan/umap-learn)
pyproject.toml              Editable install config for src/ layout
alembic.ini                 Alembic configuration
migrations/                 Alembic environment and versioned migrations
render.yaml                 Render Blueprint -- frontend static site only
Dockerfile.cloudrun         Cloud Run backend image (CPU-only torch, baked embedding model)
cloudbuild.cloudrun.yaml    Cloud Build config -- builds Dockerfile.cloudrun for linux/amd64
.dockerignore / .gcloudignore  Build-context exclusions (secrets, backups, caches)
scripts/
  run_sample_ingestion.py   Small controlled arXiv sample (<=25 papers)
  plan_backfill.py          Plan-only adaptive backfill window generation
  run_quota_ingestion.py    Execute mode: quota-limited new+historical ingestion
  run_embedding_backfill.py Generates embeddings for papers missing them
  run_paper_clustering.py   HDBSCAN/UMAP clustering + LLM cluster labeling
  run_trend_analysis.py     Historical Cohort Comparison trend pipeline
  bake_embedding_model.py   Bakes the pinned embedding model into the Cloud Run image
src/research_platform/
  config.py                 DATABASE_URL, embedding, CORS, and pacing/backfill config from env
  api/                      FastAPI app, routes, schemas
  db/                       SQLAlchemy Base, session, ORM models
  ingestion/                arXiv client, pacing, backfill planning, quota orchestration
  embeddings/               BGE model loader, semantic search, similar-papers
  clustering/               HDBSCAN/UMAP pipeline, LLM labeling, read queries
  trends/                   Historical Cohort Comparison pipeline, classification, scoring
  enrichment/                OpenAlex / Semantic Scholar enrichment
frontend/                   React + TypeScript + Vite + TanStack Query dashboard
```

## What is intentionally not here yet

RAG (retrieval-augmented generation over paper full text) is not
implemented -- the platform never downloads, stores, or parses PDF
content; "Open PDF" links point directly to arXiv. The full 2016-present
historical backfill has not been run -- the current corpus is a controlled
169-paper sample (two ingestion cohorts: January 2016 and July 2026, used
as the comparison/recent cohorts for trend analysis).
