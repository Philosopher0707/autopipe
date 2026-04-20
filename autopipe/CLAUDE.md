# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Environment Setup

**Core library** uses the `pipeline` conda env. **Dashboard backend** uses its own `.venv` (Python 3.12). Do NOT use bare `python` — it's aliased to anaconda in `.zshrc`.

```bash
conda activate pipeline                   # Core library env
cd autopipe/dashboard/backend && source .venv/bin/activate  # Backend env
```

## Build, Run, and Test Commands

### Core Library (autopipe Python package)
```bash
conda run -n pipeline pip install -e ".[dev]"   # Install with dev dependencies
conda run -n pipeline pytest tests/unit -q       # Unit tests (33 pass, 10 known failures)
conda run -n pipeline pytest tests/integration -m integration  # Integration tests
conda run -n pipeline ruff check autopipe tests   # Lint
conda run -n pipeline black --check autopipe tests # Format check
conda run -n pipeline mypy autopipe               # Type check
```

### Dashboard Backend (FastAPI)
```bash
cd autopipe/dashboard/backend
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8765 --reload  # Dev server
.venv/bin/python -m app.seed                                                     # Seed database
.venv/bin/python -m pytest tests/ -v                                            # Run 48 tests
```
- API docs: `http://localhost:8765/api/v1/docs`
- Default credentials: `admin` / `admin123`
- Tests use in-memory SQLite with `httpx.AsyncClient` + `ASGITransport`, dependency overrides for `get_db`

### Dashboard Frontend (React + Vite)
```bash
cd autopipe/dashboard/frontend
pnpm install          # Install dependencies
pnpm dev              # Dev server on :3000, proxies /api → :8765
pnpm build            # Production build → dist/
pnpm typecheck        # TypeScript check (tsc --noEmit)
pnpm test             # Run 34 tests
pnpm test:watch       # Run tests in watch mode
pnpm test:coverage    # Run tests with coverage
```

## Architecture

Three independent subsystems sharing data concepts but not code:

1. **autopipe core** (`autopipe/core/`) — Pipeline orchestration engine. `Pipeline` manages a DAG of `Step` objects, runs via topological sort. Pipelines defined in Python or YAML. LLM adapters in `autopipe/llm/`. CLI: `autopipe run <file>`.

2. **Dashboard Backend** (`autopipe/dashboard/backend/`) — FastAPI + SQLAlchemy 2.0 (async) + SQLite. REST API at `/api/v1/` with JWT auth. The executor (`app/executor/`) bridges dashboard runs to `autopipe.core.Pipeline`: loads pipeline configs via `autopipe.core.loader`, runs steps sequentially in a background thread, creates/updates Step records, and broadcasts status changes over WebSocket. Uses sync SQLAlchemy sessions in background threads (separate from async app sessions). Models: Pipeline → Runs → Steps, Experiment → Runs, Model → Versions, DriftReport → Alerts, ChartArtifact.

3. **Dashboard Frontend** (`autopipe/dashboard/frontend/`) — React 18 + TypeScript + Vite + Tailwind + TanStack Query + Zustand. Path alias `@/` → `src/`. Lazy-loaded route components. Axios client with JWT interceptor.

## Key Patterns

### Backend
- UUID string primary keys, `datetime.utcnow` timestamps, JSON columns for flexible config/metrics/tags
- Schemas: `Base → Create → Update → InDB → Response` + `PaginatedResponse` wrapper
- Pagination: `?page=1&page_size=20` (defaults from settings)
- Experiment status is **derived** from runs (not stored): no runs=pending, any running=running, any success=completed
- Run numbers are per-experiment sequential, not global
- `POST /experiments/{id}/trials` generates trial runs from experiment.config.search_space; when `simulate=false`, dispatches to the executor with trial params as `initial_inputs`
- `Base.metadata.create_all()` auto-creates tables on startup
- WebSocket at `/api/v1/ws/dashboard` and `/api/v1/ws/runs/{run_id}` — channel-based pub/sub via `ConnectionManager`; broadcast helpers (`broadcast_run_status`, `broadcast_run_log`, `broadcast_run_metric`) in `websocket.py`
- Dashboard endpoints return empty data when DB is empty (no mock fallbacks)
- `pipelines.running` in `/dashboard/overview` counts distinct pipelines with active runs (not total running runs)
- `drift.alerts_today` filters by created_at within 24h; `drift.features_drifted` does NOT fall back to alert count
- **Pipeline Executor** (`app/executor/`):
  - `runner.py`: `execute_run()` spawns a daemon thread; runs pipeline steps sequentially with per-step DB tracking and WebSocket broadcasts
  - `registry.py`: Thread-safe dict of `threading.Event` per active run — `PATCH /runs/{id}` with `status=cancelled` signals the executor to skip remaining steps
  - `_WebSocketLogHandler`: Captures `autopipe` logger output during step execution and broadcasts via WebSocket
  - `asyncio.run_coroutine_threadsafe()` bridges sync thread → async event loop for WebSocket broadcasts
  - Pipeline config must have `"steps"` key to trigger actual execution; otherwise runs stay PENDING
- `GET /experiments/{id}/compare?metric=X` — compares runs by metric, returns run IDs with metric values and params
- `count_drifted_features()` helper in `dashboard.py` deduplicates drift-counting logic across `/overview` and `/counts` endpoints
- DriftReport queries use column-level selects (`select(DriftReport.drift_score, DriftReport.feature_drifts)`) instead of full ORM loads

### Frontend
- API clients in `src/api/endpoints/` (one file per domain: pipelines, runs, experiments, models, drift, charts, websocket)
- TanStack Query with 5-min stale time, 2 retries
- Auth state via Zustand with `persist` middleware (localStorage)
- Component library in `src/components/ui/` (shadcn/ui-inspired with Radix primitives)
- Tailwind with HSL CSS variables for theming (dark/light mode)
- WebSocket client (`wsClient` singleton in `src/api/endpoints/websocket.ts`): auto-reconnect with exponential backoff, channel-based pub/sub
- RunDetail page uses WebSocket for real-time log streaming, step/status updates; falls back to 3s HTTP polling when WS disconnected
- `getStatusBgColor()` in `src/utils/helpers.ts` is the single source of truth for status badge colors — always use it, never inline color ternaries
- `useMemo` for derived data: bestRun, run status counts, metricName computed from runs array
- `useMutation.data` preferred over separate state for mutation results (e.g., compare in ExperimentDetail)
- Conditional query `enabled` flags to avoid unnecessary fetches (e.g., `pipelinesData` only when trials dialog open)

### Seeding
`python -m app.seed` creates: 4 users, 6 pipelines, 15 runs with steps, 3 experiments (linked to runs), models with versions, drift reports with alerts, chart artifacts. Experiments must be seeded BEFORE runs for linking to work.

### Docker & Deployment
- `docker-compose.yml` at `autopipe/dashboard/`: backend (port 8765), frontend (nginx on :3000), Postgres, Redis
- Frontend multi-stage Dockerfile: node:20-slim build → nginx:alpine serve
- nginx.conf: SPA fallback (`try_files $uri $uri/ /index.html`), static asset caching, API proxy to `backend:8000`, WebSocket proxy at `/ws/`

### CI (GitHub Actions)
- `test` job: 3 OS × 4 Python versions, ruff/black/mypy/bandit, pytest with coverage
- `integration` job: runs on push to main only
- `build` job: package build + twine check
- `frontend` job: pnpm install/typecheck/test/build in `autopipe/dashboard/frontend/`

## Port Configuration

The backend dev server runs on **8765** (not 8000). The frontend Vite proxy targets `:8765`. Docker-compose also maps backend to 8765.

## Commit Style

Conventional Commits: `feat`, `fix`, `feat(dashboard)`, `fix(frontend)`, `security`. Keep subjects specific to the changed surface.