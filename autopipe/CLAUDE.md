# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build, Run, and Test Commands

### Core Library (autopipe Python package)
```bash
pip install -e ".[dev]"                    # Install with dev dependencies
pytest tests/unit --cov=autopipe           # Unit tests with coverage
pytest tests/integration -m integration   # Integration tests
ruff check autopipe tests                 # Lint
black --check autopipe tests               # Format check
mypy autopipe                             # Type check
```

### Dashboard Backend (FastAPI)
```bash
cd autopipe/dashboard/backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8765 --reload   # Dev server (port 8765)
python -m app.seed                                          # Seed database
```
- API docs: `http://localhost:8765/api/v1/docs`
- Default credentials: `admin` / `admin123`

### Dashboard Frontend (React + Vite)
```bash
cd autopipe/dashboard/frontend
pnpm install          # Install dependencies
pnpm dev              # Dev server on :3000, proxies /api → :8765
pnpm build            # Production build → dist/
pnpm typecheck        # TypeScript check (tsc --noEmit)
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
- WebSocket at `/api/v1/ws/dashboard` and `/api/v1/ws/runs/{run_id}`
- **Pipeline Executor** (`app/executor/`):
  - `runner.py`: `execute_run()` spawns a daemon thread; runs pipeline steps sequentially with per-step DB tracking and WebSocket broadcasts
  - `registry.py`: Thread-safe dict of `threading.Event` per active run — `PATCH /runs/{id}` with `status=cancelled` signals the executor to skip remaining steps
  - `_WebSocketLogHandler`: Captures `autopipe` logger output during step execution and broadcasts via WebSocket
  - `asyncio.run_coroutine_threadsafe()` bridges sync thread → async event loop for WebSocket broadcasts
  - Pipeline config must have `"steps"` key to trigger actual execution; otherwise runs stay PENDING

### Frontend
- API clients in `src/api/endpoints/` (one file per domain: pipelines, runs, experiments, models, drift, charts)
- TanStack Query with 5-min stale time, 2 retries
- Auth state via Zustand with `persist` middleware (localStorage)
- Component library in `src/components/ui/` (shadcn/ui-inspired with Radix primitives)
- Tailwind with HSL CSS variables for theming (dark/light mode)

### Seeding
`python -m app.seed` creates: 4 users, 6 pipelines, 15 runs with steps, 3 experiments (linked to runs), models with versions, drift reports with alerts, chart artifacts. Experiments must be seeded BEFORE runs for linking to work.

## Port Configuration

The backend dev server runs on **8765** (not 8000 as start.sh says). The frontend Vite proxy targets `:8765`. If you start the backend with `start.sh` it uses port 8000 — override with `--port 8765`.

## Commit Style

Conventional Commits: `feat`, `fix`, `feat(dashboard)`, `fix(frontend)`, `security`. Keep subjects specific to the changed surface.