# Python Patterns — Autopipe

## Pydantic
- Use `BaseModel` for all config, request, and response shapes.
- Use `Field(description=..., ge=..., le=...)` for validation and documentation.
- Prefer `model_validate()` (v2) over deprecated `parse_obj()`.
- Use `@model_validator(mode="after")` for cross‑field validation.

## Click CLI
- Define commands in `autopipe.cli`.
- Use `@click.option("--foo", type=click.Path(exists=True), help="...")`.
- Return `click.echo()` for simple output; `rich` for tables/progress.
- Keep CLI functions thin; delegate to core services.

## Rich UI
- Use `rich.console.Console` for colored output.
- Use `rich.table.Table` for structured data (`pipelines list`, `steps inspect`).
- Use `rich.progress.Progress` for long‑running pipeline operations.
- Use `rich.panel.Panel` for CLI help banners.

## Async
- Core pipeline runner is async; steps can be sync or async.
- Wrap sync CPU‑bound work with `asyncio.to_thread()`.
- Use `tenacity` for retry decorators:
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
async def call_llm(...) -> str:
    ...
```

## NumPy / Pandas
- Validate shapes and dtypes before heavy operations.
- Avoid silent type coercion (`df["col"] = df["col"].astype(float)` explicitly).
- Prefer vectorized ops over Python loops.

## Error Handling
- Custom exceptions live in `autopipe.exceptions`.
- Catch specific exceptions; never bare `except:`.
- Use `raise MyError("...") from original` to preserve chain.

## Logging
- Use `structlog.get_logger()` everywhere.
- Bind context keys at the step level (`logger.bind(step="normalize")`).
- JSON format in CI/prod; console‑rendered in local dev.
