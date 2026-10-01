# Contributing to AutoPipe

Thanks for your interest in improving AutoPipe! This document covers the
practical rules. The project has **three independent subsystems** that share
data concepts but not code — always state which one you're touching:

1. **Core library** (`autopipe/`) — pipeline orchestration engine, ML steps,
   registry, monitoring, LLM clients, CLI.
2. **Dashboard backend** (`autopipe/dashboard/backend/`) — FastAPI + async
   SQLAlchemy + SQLite/Postgres API with a thread-based pipeline executor.
3. **Dashboard frontend** (`autopipe/dashboard/frontend/`) — React 18 +
   TypeScript + Vite + TanStack Query.

## Development setup

Core library (any Python ≥ 3.10 environment):

```bash
pip install -e ".[dev]"
```

Dashboard backend (its own virtualenv):

```bash
cd autopipe/dashboard/backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e ../../..   # core, from the REPO ROOT — see note
```

> **Why the `-e ../../..` step is required.** The backend imports the core
> library in at least four modules (`app/core/provenance.py`,
> `app/db/models.py`, `app/executor/runner.py`, `app/api/v1/endpoints/runs.py`),
> so `requirements.txt` alone cannot run it or its tests. Use the **repo root**
> (`../../..` relative to `autopipe/dashboard/backend`), not `../..` — `../..`
> is the inner `autopipe/` package directory, which has no `pyproject.toml` and
> fails the install. Installing core is also what supplies `pandas`, `numpy`
> and `pydantic`: `autopipe/core/__init__.py` imports `steps.py`, which imports
> `pandas` at module level, and the backend's `requirements.txt` does not list
> core's dependencies.

Dashboard frontend:

```bash
cd autopipe/dashboard/frontend
pnpm install
```

## Running the checks

Everything CI runs, runnable locally:

```bash
# Core library
ruff check autopipe tests          # lint (zero violations expected)
ruff format --check autopipe tests # formatting (ruff-format is the only formatter)
pytest tests/unit -q               # unit suite
pytest tests/integration -v        # integration suite

# Dashboard backend
cd autopipe/dashboard/backend && .venv/bin/python -m pytest tests/ -q
# (needs the `-e ../../..` core install above — see the note)

# Dashboard frontend
cd autopipe/dashboard/frontend
pnpm lint && pnpm typecheck && pnpm test && pnpm build
```

## Ground rules

- **No fabricated data.** Endpoints and steps must return real results or an
  honest empty state / `501 Not Implemented` — never random or hardcoded
  values presented as measurements. This is the project's most important rule.
- **Every advertised feature exists.** If you document it, implement it; if
  you can't implement it, don't document it.
- **Tests travel with behavior.** New behavior ships with tests using the
  markers `unit`, `integration`, `slow`, `requires_llm`. Coverage gate is 80%.
- **Surgical changes.** Match existing style (4-space indent, 100-char lines,
  snake_case, PascalCase classes). Don't refactor adjacent code you didn't
  touch.
- **Secrets stay in `.env`** (see `.env.example`). Never commit credentials;
  pre-commit runs gitleaks.
- Mark tests that call real LLM providers with `requires_llm` so they stay
  opt-in.

## Commits & pull requests

We use Conventional Commits with a scope for the surface touched:
`feat(core):`, `fix(backend):`, `fix(frontend):`, `chore(repo):`,
`security:`. Keep subjects specific and imperative.

PRs should describe the behavior change, list the validation commands you
ran, link any related issue, and include screenshots for dashboard/UI work.

## Reporting bugs

Open an issue with: what you ran, what you expected, what happened, and the
smallest reproduction you can manage. For pipeline YAML problems, include the
config and the full traceback.
