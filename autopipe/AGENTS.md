# Repository Guidelines

## Project Structure & Module Organization
This directory contains the `autopipe` Python package: core orchestration in `core/`, reusable steps in `steps/`, and support code in `caching/`, `config/`, `credentials/`, `monitoring/`, `observability/`, `registry/`, `schemas/`, `tracking/`, `tuning/`, and `visualization/`. Repo-level tests live in `../tests/unit/` and `../tests/integration/`;. Example configs and scripts live in `../examples/`. The dashboard lives in `dashboard/backend/` (FastAPI) and `dashboard/frontend/` (React + Vite). Do not hand-edit `dashboard/backend/static/`; rebuild the frontend instead.

## Build, Test, and Development Commands
From the repository root:

- `pip install -e ".[dev]"` installs the package plus pytest, Ruff, mypy, and security tooling.
- `pytest tests/unit --cov=autopipe --cov-report=term-missing` runs the main Python test suite with coverage.
- `pytest tests/integration -v --timeout=300` runs slower end-to-end checks.
- `ruff check autopipe tests && ruff format --check autopipe tests && mypy autopipe` matches the CI quality gates.
- `cd autopipe/dashboard/backend && pip install -r requirements.txt && uvicorn app.main:app --reload` starts the dashboard API.
- `cd autopipe/dashboard/frontend && pnpm install && pnpm dev` runs the dashboard UI locally.
- `cd autopipe/dashboard/frontend && pnpm build && pnpm typecheck` verifies production build health.
- `autopipe eval --compare` runs promptfoo LLM evaluations across your configured Ollama models (kimi, glm, minimax).
- `autopipe eval --task pipeline-generation --provider ollama-kimi` runs a subset of evaluations.
- `npx promptfoo@latest eval -c promptfoo/promptfooconfig.yaml` runs promptfoo directly via Node.js.

## LLM Evaluation
AutoPipe integrates **[promptfoo](https://promptfoo.dev)** to systematically compare the three configured Ollama models on pipeline-specific tasks:

```bash
# Full comparison across all configured models
autopipe eval --compare

# Evaluate only pipeline-generation prompts
autopipe eval --task pipeline-generation

# Output JSON
autopipe eval --compare --output results.json --verbose
```

NOTE: the `--provider` alias filter (`ollama-kimi` etc.) does not currently
match the provider IDs in `promptfooconfig.yaml`; prefer `--config` or
`--task` until fixed.

Evaluation tasks include:
- **pipeline-generation** — Generate valid AutoPipe YAML configs from natural language
- **step-explanation** — Explain what pipeline steps do
- **error-diagnosis** — Suggest fixes for common pipeline errors

All results are summarized with pass/fail rates per model.

## Coding Style & Naming Conventions
Use 4-space indentation in Python, explicit type hints, and `snake_case` for modules, functions, and variables; classes use `PascalCase`. Ruff is the single linter AND formatter (100-character lines, import order); mypy runs in strict mode on core modules. In the frontend, keep React components and page files in `PascalCase.tsx`, colocate API clients under `src/api/`, and use descriptive store names like `authStore.ts`.

## Testing Guidelines
Name tests `test_*.py` and mirror the package structure under `../tests/unit/` where practical. Use the configured pytest markers: `unit`, `integration`, `slow`, and `requires_llm`. Coverage fails below 80%, so new behavior should ship with tests or a clear justification. For dashboard changes, follow `dashboard/INTEGRATION_TESTS.md` and include manual verification notes if no automated UI test was added.

## Commit & Pull Request Guidelines
Recent history follows short, imperative Conventional Commit prefixes such as `feat`, `fix`, `fix(frontend)`, and `security`. Keep the subject line specific to the changed surface. PRs should describe the behavior change, list validation commands run, link any related issue, and include screenshots for dashboard or UI work.

## Security & Configuration Tips
Keep secrets in `.env`, never in source. Start from `.env.example` when adding configuration, and mark tests that require real provider credentials with `requires_llm` so they stay opt-in.
