# CLAUDE.md

## Karpathy Principles for AutoPipe

**Think Before Coding.** State assumptions about which subsystem you're touching (core / backend / frontend). The codebase has THREE independent subsystems sharing concepts but not code. If a change spans all three, clarify scope first.

**Simplicity First.** A new pipeline step is ~20-50 lines. A new backend endpoint is ~30 lines. A new frontend page is a lazy-loaded component. If you're writing 200 lines, simplify.

**Surgical Changes.** Touch only what you must. Core changes stay in `autopipe/`. Backend changes stay in `autopipe/dashboard/backend/`. Frontend changes stay in `autopipe/dashboard/frontend/`. Match existing style (4-space indent, 100-char lines, snake_case, strict mypy). Do NOT refactor adjacent code or "improve" formatting you didn't touch.

**Goal-Driven Execution.** Every task needs verifiable success criteria:
- "Add a step" → "Step class + unit test + pytest passes"
- "Fix backend bug" → "Repro test → passes → full backend suite passes"
- "Add dashboard feature" → "API endpoint + frontend page + integration test"
- "Refactor" → "All tests pass before AND after"

---

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
conda run -n pipeline pytest tests/unit -q       # Unit tests (205 pass, 2 skipped)
conda run -n pipeline pytest tests/integration -m integration  # Integration tests
conda run -n pipeline ruff check autopipe tests   # Lint
conda run -n pipeline ruff format --check autopipe tests  # Format check (ruff-format is the only formatter)
conda run -n pipeline mypy autopipe               # Type check
```

### Dashboard Backend (FastAPI)
```bash
cd autopipe/dashboard/backend
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8765 --reload  # Dev server
.venv/bin/python -m app.seed                                                     # Seed database
.venv/bin/python -m alembic upgrade head                                        # Apply DB migrations
.venv/bin/python -m alembic revision --autogenerate -m "..."                    # New migration
.venv/bin/python -m alembic stamp head                                          # Adopt an existing (create_all) DB
.venv/bin/python -m pytest tests/ -v                                            # Run backend tests
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
- `GET /charts/training-metrics-trace?run_id={id}` — queries `MetricLog` for `loss`/`val_loss`/`accuracy`/`val_accuracy` grouped by `step_index` as epoch; falls back to `ChartArtifact.data.points` if no logs; returns `TrainingMetricsTraceResponse`
- `count_drifted_features()` lives in `app/utils/drift_utils.py` and delegates to `normalize_feature_drifts()` — ONE drift-verdict interpretation for `/overview`, `/counts`, and charts; the detector's stored `drift_detected` wins over re-derivation
- DriftReport queries use column-level selects (`select(DriftReport.drift_score, DriftReport.feature_drifts)`) instead of full ORM loads
- `normalize_feature_drifts()` lives in `app/utils/drift_utils.py` — shared by both `drift.py` and `charts.py`; do NOT duplicate inline
- **Explainability API** (`/api/v1/explainability/`): `POST /shap` and `POST /lime` accept `model_id` + `data` payload, return `feature_importance` arrays
- **AutoML API** (`/api/v1/trials/`): `GET /trials` (list), `GET /trials/{id}` (detail), `GET /trials/{id}/history` (optimization history); return trial records with `number`, `state`, `value`, `params` JSON, `datetime`
- **Features API** (`/api/v1/features/`): `POST /features/extract` (apply transforms, return before/after stats + sample values), `GET /features/preview/{pipeline_id}` (preview pipeline stats)

### Frontend
- API clients in `src/api/endpoints/` (one file per domain: pipelines, runs, experiments, models, drift, charts, websocket, automl, features)
- TanStack Query with 5-min stale time, 2 retries
- Auth state via Zustand with `persist` middleware (localStorage)
- Component library in `src/components/ui/` (shadcn/ui-inspired with Radix primitives)
- Tailwind with HSL CSS variables for theming (dark/light mode)
- WebSocket client (`wsClient` singleton in `src/api/endpoints/websocket.ts`): auto-reconnect with exponential backoff, channel-based pub/sub; `disconnect()` sets `reconnectAttempts = maxReconnectAttempts` to prevent reconnect after intentional close
- RunDetail page uses WebSocket for real-time log streaming, step/status updates; falls back to 3s HTTP polling when WS disconnected; uses `wsConnectedRef` (ref) not state to avoid render loops; `apiLogs` effect skips when WS connected
- Vite proxy for `/api` includes `ws: true` to forward WebSocket connections (no separate `/ws` proxy needed)
- `TrainingMetricsChart` in `src/components/charts/TrainingMetricsChart.tsx` — tabbed Recharts `LineChart` for loss/accuracy curves; queries `GET /charts/training-metrics-trace`; Loss tab shows Train (red) + Validation (blue); Accuracy tab shows Train (green) + Validation (purple); conditionally renders only when `points.length > 0` and metrics exist
- `getStatusBgColor()` in `src/utils/helpers.ts` is the single source of truth for status badge colors — always use it, never inline color ternaries
- `useMemo` for derived data: bestRun, run status counts, metricName computed from runs array
- `useMutation.data` preferred over separate state for mutation results (e.g., compare in ExperimentDetail)
- Conditional query `enabled` flags to avoid unnecessary fetches (e.g., `pipelinesData` only when trials dialog open)
- **AutoMLPage** (`/automl`) — tabbed: trial history table, param importance bar chart (Recharts), Pareto front scatter plot, pruning history line chart; uses `automlApi` client
- **FeaturesPage** (`/features`) — tabbed: transform pipeline builder with +Add Step buttons, before/after feature stats tables, feature distribution histogram (Recharts); uses `featuresApi` client
- **ExplainabilityPage** (`/explainability`) — tabbed: SHAP beeswarm scatter, LIME force bar chart, permutation importance bar chart

### Seeding
`python -m app.seed` creates: 4 users, 6 pipelines, 15 runs with steps, 3 experiments (linked to runs), models with versions, drift reports with alerts, chart artifacts, `MetricLog` training curves (10 epochs of loss/val_loss/accuracy/val_accuracy for each successful run). Experiments must be seeded BEFORE runs for linking to work.

### Docker & Deployment
- `docker-compose.yml` at `autopipe/dashboard/`: backend (port 8765, context `./backend`), frontend (nginx on :3000), Postgres, Redis
- Frontend multi-stage Dockerfile: node:20-slim build → nginx:alpine serve
- nginx.conf: SPA fallback, static asset caching, API + WebSocket proxy via `/api/` block (includes Upgrade headers)
- DB session (`app/db/session.py`) auto-detects SQLite vs Postgres and uses appropriate async driver (aiosqlite vs asyncpg)
- Backend `requirements.txt` includes both `aiosqlite` (dev/SQLite) and `asyncpg`+`psycopg2-binary` (Docker/Postgres)
- `/dashboard/health` endpoint performs real DB connectivity check (`select(1)`) and autopipe_core import check; no fake Redis check
- Backend tests live in `dashboard/backend/tests/` and run via the dedicated `backend` CI job
- 34 frontend tests

### Workspace Panels
The `/workspace` route provides a multi-panel layout with 14 panel types for run analysis and visualization:
- `line-plot`, `bar-chart`, `scatter-plot` — Metric visualization via Recharts
- `param-importance` — Parameter comparison table
- `metric-summary` — Best-run metric cards
- `confusion-matrix` — Classification confusion matrix (from run config)
- `run-table` — Sortable/filterable runs table
- `run-comparison` — Multi-run comparison with parameter diffs and metric sparklines (`POST /runs/compare`)
- `histogram` — Metric distribution histogram (`GET /charts/available-metrics`)
- `parallel-coords` — Parallel coordinates for hyperparameter visualization
- `media-viewer` — Image gallery from run config media
- `dataframe-table` — Data preview table from run config
- `text-log` — Log tail viewer (`GET /runs/{id}/logs?tail=N`)

Panel renderers receive `{ panel }` prop with `PanelLayout` type (id, type, title, config, state). Each panel uses `PanelWrapper` for consistent chrome, loading skeletons, and error boundaries. Panel state is persisted via Zustand store.

### Security (Backend)
- Router-level JWT enforcement: every data router under `/api/v1/` requires a valid
  access token (`dependencies=[Depends(get_current_user)]`); only `/auth/*` is public
- Destructive routes (DELETEs, model promote, alert acknowledge) additionally require
  `require_role("admin")`
- Registration never trusts client-sent roles: first account bootstraps admin, later
  accounts start as `data_scientist`
- WebSocket handshakes require the access token as `?token=` query param (browsers
  cannot set headers on WS); rejected with close code 1008 before accept
- Legacy SHA256 password hashes are transparently upgraded to bcrypt on login
- `SECRET_KEY` must come from env in production (random per-process default invalidates
  tokens on restart); token TTL is 24h
- `app/core/security.py` — `SimpleRateLimiter` (in-memory), rate-limit decorator for login/register endpoints, bcrypt password hashing with legacy SHA256 fallback for existing seeds
- `app/core/security_headers.py` — `SecurityHeadersMiddleware` adds CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy
- `app/core/file_security.py` — Path traversal prevention, mime type validation, safe file serving utilities
- Tests in `tests/test_security.py` (25 tests covering all three modules)

### CI (GitHub Actions)
- `test` job: 3 OS × 3 Python (3.10–3.12), ruff lint + ruff-format + enforced mypy strict on `autopipe/core` + bandit, pytest with coverage
- `integration` job: runs on every push and PR (uses pytest-timeout)
- `build` job: package build + twine check
- `frontend` job: pnpm install/typecheck/test/build in `autopipe/dashboard/frontend/`

## Port Configuration

The backend dev server runs on **8765** (not 8000). The frontend Vite proxy targets `:8765`. Docker-compose also maps backend to 8765.

## Eval Command

`autopipe eval` — LLM evaluation via promptfoo or direct Ollama fallback.

```bash
autopipe eval --config promptfoo/promptfooconfig.yaml
autopipe eval --task pipeline-generation --model kimi-k2.5:cloud
autopipe eval --compare --output eval-results.json
```

Requires Node.js + promptfoo. NOTE: the `--provider` alias filter (`ollama-kimi` etc.) does not currently match the provider IDs declared in `promptfoo/promptfooconfig.yaml` — known issue, scheduled for the P3 safety pass.

## Commit Style

Conventional Commits: `feat`, `fix`, `feat(dashboard)`, `fix(frontend)`, `security`. Keep subjects specific to the changed surface.