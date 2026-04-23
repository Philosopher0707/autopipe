# Pipeline Patterns — Autopipe

## Skill: pipeline-patterns

## When to Apply
- Designing a new pipeline step.
- Writing or editing YAML pipeline configs.
- Extending the core runner, loader, or step registry.

## Core Architecture

### 1. Step Lifecycle
```python
from autopipe.core.step import Step

class MyStep(Step):
    name: str = "my_step"
    description: str = "Does a thing"

    async def run(self, ctx: PipelineContext) -> dict:
        data = ctx.get("previous_output")
        result = await self.transform(data)
        return {"my_step_output": result}
```
- Keep `run()` under ~50 lines of business logic.
- Offload heavy work to helpers in the same file or `autopipe.core.utils`.
- Return a flat `dict` so downstream steps can access keys directly.

### 2. YAML Configs
Pipeline configs live in the repo root or `examples/`:
```yaml
name: "feature_engineering"
steps:
  - name: "load_csv"
    type: "autopipe.steps.data.LoadCSV"
    params:
      path: "data/input.csv"
  - name: "normalize"
    type: "autopipe.steps.preprocess.Normalize"
    depends_on: ["load_csv"]
```
- Every `type` string must be resolvable by `autopipe.core.loader`.
- Prefer explicit `depends_on` over implicit ordering.
- Validate against JSON schemas in `autopipe/schemas/` before execution.

### 3. Context & Observability
- Use `PipelineContext` to share data; avoid global state.
- Log with `structlog` (JSON in production, human in dev).
- Emit OpenTelemetry spans around step execution (`opentelemetry-api`).
- Metrics (timers, counters) go through `prometheus-client`.

### 4. Error Handling
- Steps raise `autopipe.exceptions.PipelineError` or subclasses.
- The runner catches exceptions and writes state to `lab-outputs/` for debugging.
- Always include the step name and input shape in error messages.

### 5. CLI Entry Points
- `autopipe run --config pipeline.yaml`
- `autopipe validate --config pipeline.yaml` (dry run)
- `autopipe inspect --config pipeline.yaml` (print DAG)

## Anti‑Patterns
- ** DON'T ** mutate the input `ctx` dict in place without copying critical fields.
- ** DON'T ** block the event loop inside `run()`; use `asyncio.to_thread()` for CPU‑bound numpy/pandas work.
- ** DON'T ** hardcode paths; accept `params` and validate via `Path`.
- ** DON'T ** import backend modules inside core steps.

## Quick Commands
```bash
# Validate a pipeline config
conda run -n pipeline autopipe validate --config example_pipeline.yaml

# Dry run
conda run -n pipeline autopipe run --config example_pipeline.yaml --dry-run

# Run with full observability
conda run -n pipeline autopipe run --config example_pipeline.yaml --verbose
```
