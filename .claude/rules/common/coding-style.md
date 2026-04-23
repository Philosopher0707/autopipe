# Common Coding Style

Universal conventions for the Autopipe codebase.

## Formatting
- Indent with **4 spaces** (no tabs).
- Max line length **100 characters** (`black`, `ruff`, `isort` enforce this).
- Use trailing commas in multi‑line collections.

## Naming
- `snake_case` for modules, functions, variables.
- `PascalCase` for classes.
- `UPPER_SNAKE_CASE` for module‑level constants.
- Descriptive names > abbreviations (`data_loader` over `dl`).

## Imports
- Group order: stdlib → third‑party → first‑party (`autopipe`).
- `isort` + `ruff` handle grouping; do NOT manually reorder unless fixing a conflict.
- Avoid `from module import *`; be explicit.

## Principles
- **Immutability**: prefer dataclasses with `frozen=True`, Pydantic models, or plain dicts that you copy before mutating.
- **KISS**: a pipeline step is 20–50 lines; a CLI command handler is ~30 lines.
- **DRY**: extract helpers after duplication appears twice.
- **YAGNI**: do not add abstraction for hypothetical futures.

## File Organization
- One major class or group of related functions per file.
- Mirror `autopipe/` package structure under `tests/unit/`.
- Dashboard backend keeps its own `tests/` inside `dashboard/backend/`.
- Dashboard frontend colocates components, pages, and API clients.
