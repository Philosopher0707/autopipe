# Testing Standards — Python

## Structure
- Tests live in `tests/unit/` and `tests/integration/`.
- Mirror the `autopipe/` package path under `tests/unit/`.
- Shared fixtures go in `tests/conftest.py`.

## Naming
- File: `test_*.py`
- Class: `Test*` (rarely used; prefer free functions).
- Function: `test_*`.

## Markers
Use the configured markers:
- `@pytest.mark.unit` — default, fast, isolated.
- `@pytest.mark.integration` — end‑to‑end, may hit real APIs.
- `@pytest.mark.slow` — skip with `-m "not slow"`.
- `@pytest.mark.requires_llm` — needs real provider credentials; opt‑in.

## Coverage
- `pytest --cov=autopipe --cov-report=term-missing`
- Minimum **80%** (`fail_under = 80` in `pyproject.toml`).
- New behavior must ship with tests or a clear justification in PR.

## Mocking
- Use `pytest-mock` (`mocker.patch`, `mocker.patch.object`).
- Mock external I/O: LLM APIs, file system, HTTP, databases.
- Use `AsyncMock` for async functions.
- Keep mock scope narrow; patch the consumer, not the library internals.

## Async Tests
```python
import pytest

@pytest.mark.asyncio
async def test_step_runs(mocker):
    step = MyStep(params={"x": 1})
    mocker.patch.object(step, "fetch", return_value="mocked")
    result = await step.run(ctx={})
    assert result == {"my_step_output": "mocked"}
```

## Parameterized Tests
Use `@pytest.mark.parametrize` for matrix coverage:
```python
@pytest.mark.parametrize("input,expected", [
    ({"x": 1}, 2),
    ({"x": -1}, 0),
])
def test_transform(input, expected):
    assert transform(input) == expected
```

## CI Gates
- `pytest tests/unit -q --cov=autopipe --cov-report=term-missing`
- Must pass before merge.
