# AutoPipe — Codebase Knowledge Q&A

Generated from Mempalace semantic index + source inspection.

---

## 1. Architecture

### Q1: What are the three independent subsystems in AutoPipe?
**A:** Core library (`autopipe/`), Dashboard Backend (`autopipe/dashboard/backend/`), Dashboard Frontend (`autopipe/dashboard/frontend/`). They share data concepts but not code. *(Source: `autopipe/CLAUDE.md`)*

### Q2: How does the core pipeline engine execute steps?
**A:** `Pipeline` manages a DAG of `Step` objects and runs them via topological sort. Steps are defined in Python or YAML and resolved by `autopipe.core.loader`. *(Source: `autopipe/CLAUDE.md`, `autopipe/core/pipeline.py`)*

### Q3: What is the relationship between dashboard runs and the core pipeline?
**A:** The dashboard executor (`app/executor/`) bridges dashboard runs to `autopipe.core.Pipeline`. It loads pipeline configs via `autopipe.core.loader`, runs steps sequentially in a background thread, and broadcasts status changes over WebSocket. *(Source: `autopipe/CLAUDE.md`)*

### Q4: What does the dashboard backend use for async database access?
**A:** SQLAlchemy 2.0 async with SQLite (aiosqlite) in dev and Postgres (asyncpg) in Docker. Session auto-detects the driver. *(Source: `autopipe/dashboard/backend/app/db/session.py`)*

### Q5: What frontend stack does the dashboard use?
**A:** React 18 + TypeScript + Vite + Tailwind CSS + TanStack Query + Zustand. Path alias `@/` maps to `src/`. *(Source: `autopipe/dashboard/frontend/README.md`, `autopipe/CLAUDE.md`)*

---

## 2. Setup & Install

### Q6: How do you install the core library for development?
**A:** `conda run -n pipeline pip install -e ".[dev]"`. Do NOT use bare `python` — it's aliased to anaconda in `.zshrc`. *(Source: `autopipe/CLAUDE.md`)*

### Q7: What ports do the backend and frontend dev servers use?
**A:** Backend runs on **8765** (not 8000). Frontend Vite dev server runs on **3000** and proxies `/api` to `:8765`. *(Source: `autopipe/CLAUDE.md`)*

### Q8: How do you start the dashboard backend?
**A:**
```bash
cd autopipe/dashboard/backend
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8765 --reload
```
Then seed the database: `.venv/bin/python -m app.seed`. *(Source: `autopipe/CLAUDE.md`)*

---

## 3. API & Usage

### Q9: What is the base API path for the dashboard backend?
**A:** `/api/v1/`. OpenAPI docs at `/api/v1/docs`. *(Source: `autopipe/dashboard/backend/app/main.py`)*

### Q10: How does the frontend authenticate with the backend?
**A:** JWT tokens stored in Zustand `persist` middleware (localStorage). Axios client has a JWT interceptor that adds the `Authorization` header. *(Source: `autopipe/CLAUDE.md`)*

### Q11: What WebSocket endpoints exist?
**A:** `/api/v1/ws/dashboard` (global updates) and `/api/v1/ws/runs/{run_id}` (per-run logs/status/metrics). Channel-based pub/sub via `ConnectionManager`. *(Source: `autopipe/CLAUDE.md`)*

### Q12: How do you cancel a running pipeline from the API?
**A:** `PATCH /runs/{id}` with `status=cancelled`. The executor registry (`app/executor/registry.py`) signals a `threading.Event` to skip remaining steps. *(Source: `autopipe/CLAUDE.md`)*

---

## 4. Testing

### Q13: Where do tests live and how are they organized?
**A:** `tests/unit/` mirrors the `autopipe/` package path. Shared fixtures in `tests/conftest.py`. Dashboard backend keeps its own `tests/` inside `autopipe/dashboard/backend/`. *(Source: `.claude/rules/python/testing.md`, `autopipe/CLAUDE.md`)*

### Q14: How many tests exist and what is the coverage gate?
**A:** 82 backend tests + 34 frontend tests. Minimum coverage: **80%** (`fail_under = 80` in `pyproject.toml`). *(Source: `autopipe/CLAUDE.md`, `pyproject.toml`)*

### Q15: What markers are used for test categorization?
**A:** `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.slow`, `@pytest.mark.requires_llm`. *(Source: `.claude/rules/python/testing.md`)*

### Q16: What does the `reset_singletons` fixture do?
**A:** Resets `_credential_manager`, `_cache_instance`, and `_metrics_collector` between tests to avoid cross-test state pollution. *(Source: `tests/conftest.py`)*

---

## 5. Patterns & Conventions

### Q17: What logging library does AutoPipe use?
**A:** `structlog`. JSON format in CI/prod, console-rendered in local dev. Log context is bound at the step level (`logger.bind(step="normalize")`). *(Source: `.claude/rules/python/patterns.md`, `autopipe/utils/logging.py`)*

### Q18: What is the custom exception hierarchy?
**A:** `AutoPipeError` (base) → `ConfigurationError`, `ValidationError`, `PipelineError`, `StepError`, `DependencyError` → `CircularDependencyError`, `LLMError`. Steps should raise specific subclasses. *(Source: `autopipe/exceptions/__init__.py`)*

### Q19: What are the naming conventions?
**A:** `snake_case` for modules/functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for module-level constants. Max line length 100 characters. 4-space indent. *(Source: `.claude/rules/common/coding-style.md`)*

### Q20: How should CPU-bound work be handled in async steps?
**A:** Wrap with `asyncio.to_thread()`. Never block the event loop inside `run()`. *(Source: `.claude/rules/python/patterns.md`)*

---

## 6. Troubleshooting

### Q21: Why might a pipeline run stay in PENDING status?
**A:** The pipeline config must have a `"steps"` key to trigger actual execution. Without it, the executor does not start and the run remains PENDING. *(Source: `autopipe/CLAUDE.md`)*

### Q22: How does the frontend handle WebSocket disconnection?
**A:** Falls back to 3-second HTTP polling. The `RunDetail` page uses `wsConnectedRef` (a ref, not state) to avoid render loops. *(Source: `autopipe/CLAUDE.md`)*

### Q23: What should you do if native addons break after a Node.js upgrade?
**A:** Run `npm rebuild better-sqlite3 sqlite-vec`. *(Source: `~/.claude/CLAUDE.md`)*

---

## 7. Contribution

### Q24: What commit style does this repo use?
**A:** Conventional Commits: `feat`, `fix`, `feat(dashboard)`, `fix(frontend)`, `security`. Subjects should be specific to the changed surface. *(Source: `autopipe/CLAUDE.md`)*

### Q25: What is the required CI gate before merge?
**A:** `pytest tests/unit -q --cov=autopipe --cov-report=term-missing` must pass. *(Source: `.claude/rules/python/testing.md`)*

---

## 8. Advanced / Design Decisions

### Q26: Why does `drift.features_drifted` NOT fall back to alert count?
**A:** It uses a dedicated `count_drifted_features()` helper in `app/utils/drift_utils.py` to avoid conflating alerts with actual drifted feature counts. *(Source: `autopipe/CLAUDE.md`)*

### Q27: How is experiment status determined?
**A:** It is **derived** from runs, not stored: no runs = pending, any running = running, any success = completed. *(Source: `autopipe/CLAUDE.md`)*

### Q28: What is the `pipeline-patterns` skill for?
**A:** A Claude Code skill that provides guidance on designing pipeline steps, writing YAML configs, using `PipelineContext`, error handling, and CLI entry points. Located at `.claude/skills/pipeline-patterns/`. *(Source: `.claude/skills/pipeline-patterns/SKILL.md`)*
