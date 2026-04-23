# TDD for Python — RED GREEN REFACTOR

## Skill: tdd-python

## When to Apply
- Adding a new pipeline step, CLI command, backend endpoint, or dashboard feature.
- Fixing a bug — start with a failing test that reproduces it.
- Refactoring — ensure coverage stays ≥80%.

## Workflow

### 1. RED — Write the Failing Test
- Create or update a test under `tests/unit/` mirroring the package path.
- Name it `test_*.py` with functions named `test_*`.
- Use pytest markers: `@pytest.mark.unit`, `@pytest.mark.slow`, `@pytest.mark.integration`, `@pytest.mark.requires_llm`.
- Use fixtures from `tests/conftest.py` or module‑local fixtures.
- Mock external I/O (LLM APIs, filesystem, database) with `pytest-mock` or `unittest.mock`.
- Run and confirm failure:
```bash
conda run -n pipeline pytest tests/unit -vv -k <keyword>
```

### 2. GREEN — Minimal Implementation
- Write the simplest code that makes the test pass.
- Do NOT add unrelated features or polish.
- Run the targeted test again; confirm pass.
```bash
conda run -n pipeline pytest tests/unit -vv -k <keyword>
```

### 3. REFACTOR — Clean While Green
- Extract helpers, rename variables, reduce duplication.
- Ensure type hints are complete for public APIs.
- Run the full unit suite:
```bash
conda run -n pipeline pytest tests/unit -q --cov=autopipe --cov-report=term-missing
```
- Coverage must stay **≥80%** (`fail_under = 80` in `pyproject.toml`).

### 4. Quality Gates
```bash
# Lint + format + type check
conda run -n pipeline ruff check autopipe tests
conda run -n pipeline black --check autopipe tests
conda run -n pipeline mypy autopipe
# Full test suite
conda run -n pipeline pytest tests/unit -q --cov=autopipe --cov-report=term-missing
```

## Async Testing
- Decorate async tests with `@pytest.mark.asyncio`.
- Use `asyncio.run()` or `await` inside test bodies.
- Mock async dependencies via `AsyncMock`.

## Frontend Tests
- Dashboard frontend uses Vitest or Playwright (check `dashboard/frontend/package.json`).
- Add component tests for new UI surfaces.
- Run `pnpm test` in `autopipe/dashboard/frontend/`.

## Commit Pattern
Use Conventional Commits at each stage:
- `test: add failing test for pipeline cache`
- `feat: implement pipeline cache`
- `refactor: extract cache helper, tighten types`

## Coverage Checklist
- [ ] New behavior has at least one unit test.
- [ ] Integration tests added for cross‑subsystem flows (if applicable).
- [ ] All tests pass with `--strict-markers`.
- [ ] Coverage stays ≥80%.
- [ ] Type hints pass `mypy --strict`.
- [ ] `ruff check` and `black --check` pass.
