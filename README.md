# AI Research Intelligence and Paper Recommendation Platform

Phase 1 status: local database foundation, plus a paced arXiv ingestion
pipeline (sample ingestion, adaptive historical-backfill planning, and
quota-limited execution). Embeddings, pgvector, clustering, RAG, and any
frontend are not implemented yet.

## Prerequisites

- Docker (with Compose v2)
- Python 3.10+

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

This applies the Phase 1 baseline schema (14 tables) plus the additive
pacing/backfill/quota migration (3 more tables, 17 total). Migration config
lives in `alembic.ini` / `migrations/env.py`, which reads `DATABASE_URL` from
`.env` via `research_platform.config`.

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

# execute mode: quota-limited new+historical ingestion (capped at 100 for now)
python3 scripts/run_quota_ingestion.py --quota 100 --page-size 200
```

All arXiv API access is paced through `api_request_states` (shared across
processes/restarts) and protected by a Postgres advisory lock so only one
collector runs at a time. See `src/research_platform/ingestion/` for the
client, planner, and orchestrator.

## 6. Stopping / resetting

```bash
docker compose down          # stop, keep data volume
docker compose down -v       # stop and delete all data (destructive)
```

## Project layout

```
docker-compose.yml          Postgres-only local service
requirements.txt            Python dependencies
pyproject.toml              Editable install config for src/ layout
alembic.ini                 Alembic configuration
migrations/                 Alembic environment and versioned migrations
scripts/
  run_sample_ingestion.py   Small controlled arXiv sample (<=25 papers)
  plan_backfill.py          Plan-only adaptive backfill window generation
  run_quota_ingestion.py    Execute mode: quota-limited new+historical ingestion
src/research_platform/
  config.py                 DATABASE_URL + arXiv pacing/backfill config from .env
  db/base.py                SQLAlchemy declarative Base
  db/session.py             Engine + sessionmaker
  db/models.py               All 17 ORM models
  ingestion/
    arxiv_client.py         Paced HTTP client, retry/backoff, date-range + preflight queries
    normalize.py             Atom entry -> normalized fields, version-row builder
    upsert.py                 Idempotent canonical-paper upsert
    run_tracker.py           ingestion_runs/ingestion_failures bookkeeping
    pacing.py                 Persistent (DB-backed) request pacing
    advisory_lock.py          Single-worker Postgres advisory lock
    backfill_planner.py       Adaptive monthly/weekly/daily window planning
    quota_orchestrator.py     Quota allocation, paginated execution, checkpointing
    arxiv_job.py              Sample ingestion job (25-paper cap)
```

## What is intentionally not here yet

OpenAlex/Semantic Scholar enrichment, embeddings, pgvector, clustering
(HDBSCAN/UMAP), RAG, and any frontend. The full 2016-present historical
backfill has not been run -- only a controlled 100-paper quota test.
