# Sightline — Research Intelligence Frontend

React + TypeScript frontend for the AI Research Intelligence and Paper
Recommendation Platform. It is a **read-only** dashboard over the backend
API: browsing, searching, and exploring paper clusters. It never mutates
backend data — there are no create/update/delete requests anywhere in this
app.

## Prerequisites

- Node.js 20+ and npm
- The backend API running locally (see below) — the frontend has no
  standalone mode; every page fetches real data from it
- PostgreSQL, reachable by the backend (see the root `README.md` for
  database setup — this frontend never talks to Postgres directly)

## 1. Start PostgreSQL

From the repository root:

```bash
docker compose up -d
docker inspect --format='{{.State.Health.Status}}' research_platform_postgres
```

See the root `README.md` for full database setup (migrations, ingestion).

## 2. Start the backend API

From the repository root, with the Python virtualenv active:

```bash
source .venv/bin/activate
uvicorn research_platform.api.app:app --reload --port 8000
```

The API serves from `http://127.0.0.1:8000`. CORS is restricted to the
origins in `CORS_ALLOWED_ORIGINS` (defaults to `http://localhost:5173`, the
Vite dev server's default port — see `src/research_platform/config.py`).

## 3. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Opens at `http://localhost:5173`. No `.env` file is required for local
development — the API base URL defaults to `http://127.0.0.1:8000` (see
[Configuration](#configuration) below). To point at a different backend,
copy `.env.example` to `.env` and edit it:

```bash
cp .env.example .env
```

## Configuration

The frontend reads exactly one backend-related environment variable:

- `VITE_API_BASE_URL` — the backend API's base URL (e.g.
  `http://127.0.0.1:8000`). This is a plain host URL, never a secret.

There is no other source of backend configuration in this app, and no
backend secrets (API keys, database credentials) are ever read, stored, or
bundled into frontend code — anything under `VITE_*` is compiled into the
client bundle and shipped to the browser in plain text, so nothing sensitive
can live there.

Resolution rules (`src/api/config.ts`):
- In dev (`npm run dev`), an unset `VITE_API_BASE_URL` falls back to
  `http://127.0.0.1:8000` for convenience.
- In a production build, an unset `VITE_API_BASE_URL` throws a clear
  configuration error at runtime (module load) rather than silently
  shipping a build pointed at localhost.
- A malformed value (not a valid `http(s)` URL) throws a clear error in
  both modes.

`.env` and `.env.local` are git-ignored; only `.env.example` (containing the
non-sensitive default) is committed.

## API type generation

`src/api/types.gen.ts` is generated from the backend's live OpenAPI schema
and must never be hand-edited — it's excluded from ESLint (see
`eslint.config.js`) for that reason. Regenerate it whenever the backend API
shape changes:

```bash
npm run generate:api
```

This requires the backend to be running at `http://127.0.0.1:8000` (it
fetches `/openapi.json`). Commit the regenerated file like any other source
change.

## Commands

| Command | Purpose |
| --- | --- |
| `npm run dev` | Start the Vite dev server |
| `npm run build` | Type-check (`tsc -b`) then production-build with Vite |
| `npm run preview` | Serve the production build locally |
| `npm run lint` | ESLint (zero errors, zero warnings expected) |
| `npm run typecheck` | `tsc -b --noEmit` |
| `npm run test` | Vitest in watch mode |
| `npm run test:run` | Vitest, single run (used in CI-style checks) |
| `npm run generate:api` | Regenerate `src/api/types.gen.ts` from the live backend |

## Architecture notes

- **Stack**: React 19 + TypeScript + Vite + React Router 7 + TanStack Query
  5 + Tailwind CSS v4 (CSS-first `@theme`) + shadcn/ui (Radix-based) +
  Recharts.
- **Data fetching**: every page hook (`src/hooks/*`) wraps a TanStack Query
  call through `apiGet<T>()` (`src/api/client.ts`), a typed fetch wrapper
  around `VITE_API_BASE_URL`. `ApiError` exposes `status`/`detail` so UI
  code can distinguish 400 (bad request) / 404 (not found) / 422
  (validation) / network failures / 5xx without re-parsing responses itself.
- **Types**: all request/response shapes come from `src/api/types.gen.ts`
  (see [API type generation](#api-type-generation)); `src/api/types.ts`
  re-exports the subset the app actually uses under shorter names.
- **URL state as source of truth**: Search, Similar Papers, Research
  Clusters, Cluster Detail, and Unclustered Papers all keep their filters
  and pagination in the URL query string (`useSearchParams()`), not
  component state or navigation state. This makes every filtered/paginated
  view linkable and makes direct links (e.g. a shared cluster URL) behave
  identically to in-app navigation.
- **Code splitting**: every route page is lazy-loaded (`React.lazy` +
  `Suspense` in `App.tsx`); only the app shell (`AppShell`, `Sidebar`,
  `TopBar`) loads eagerly. See `RouteLoadingFallback` for the loading
  skeleton shown while a route chunk loads.
- **Score badges**: the app distinguishes four visually and textually
  distinct badge types that are easy to conflate — `ConfidenceBadge`
  ("Label confidence", how well an LLM-generated cluster name/description
  fits its cluster), `MembershipProbabilityBadge` ("Avg. membership", a
  cluster's average per-paper fit), `ClusterMembershipBadge` ("Cluster
  membership", a single paper's fit to its cluster), and `SimilarityBadge`
  ("Semantic similarity", embedding similarity between two papers or a
  query and a paper). Never reuse "confidence" for anything except the
  first.

## Pages

**Implemented (real backend data):**

| Route | Page |
| --- | --- |
| `/` | Dashboard — corpus stats, cluster distribution, representative papers |
| `/search` | Paper Search — semantic search with category/result-count filters |
| `/papers/:paperId/similar` | Similar Papers — a paper's detail plus its nearest neighbors |
| `/clusters` | Research Clusters — browse/search/sort all approved clusters |
| `/clusters/:clusterId` | Cluster Detail — cluster stats, category chart, member papers |
| `/clusters/noise` | Unclustered Papers — papers not confidently assigned to any cluster |
| `/settings` | Settings — placeholder; no user accounts or preferences exist yet |

**Placeholder ("Coming soon"), no backend support yet:** Trending Papers
(`/trending`), Recommendations (`/recommendations`), Authors (`/authors`),
Organizations (`/organizations`), Datasets (`/datasets`), Models (`/models`),
Daily Digest (`/digest`), Saved Papers (`/saved`). These render a generic
`ComingSoonPage` and are marked "Soon" in the sidebar (`src/lib/constants.ts`).

Any unmatched route renders `NotFoundPage`.

## Testing

Focused tests only (Vitest + React Testing Library + MSW for network-level
API mocking) — this suite intentionally does not duplicate backend tests or
attempt full end-to-end coverage. It covers:

- every route renders without error, including that `/clusters/noise`
  resolves to the noise-papers view and never gets misrouted to
  `/clusters/:clusterId`
- malformed cluster/paper IDs show invalid-link states rather than crashing
- Paper Search blocks blank/whitespace-only submissions and restores its
  query/filters from the URL on load
- Similar Papers renders correctly from a direct link with no navigation
  state
- Cluster Detail and Unclustered Papers preserve filters across
  pagination/URL changes
- the four score badges (see above) never collapse onto the same visible
  label
- `ErrorState` renders a distinct message for each of 400/404/422/network/5xx

Run with `npm run test` (watch) or `npm run test:run` (single pass).

## Known limitations

- Read-only: there is no authentication, no saved-paper persistence, and no
  way to trigger backend mutations (re-clustering, re-embedding, re-labeling)
  from the UI.
- Eight nav sections are placeholders with no backend endpoints behind them
  yet (see [Pages](#pages)).
- Research Clusters' search/filter/sort is entirely client-side (the backend
  list endpoint has no query parameters for it), so it only operates on
  clusters already fetched, not a server-side search.
