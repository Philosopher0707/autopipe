# ML Pipeline Config Rules

## YAML Pipeline Design

### Required Fields
Every pipeline YAML must declare:
- `name`: human‑readable, `snake_case`.
- `version`: semver string.
- `steps`: ordered list of step definitions.

### Step Definition
```yaml
steps:
  - name: "load"
    type: "autopipe.steps.data.LoadCSV"
    params:
      path: "data/input.csv"
      delimiter: ","
    depends_on: []           # explicit dependency list
```
- `name` is unique within the pipeline.
- `type` must resolve via `autopipe.core.loader`.
- `params` keys must match the step's Pydantic model fields.

### Validation
- Run `autopipe validate --config file.yaml` before committing new configs.
- All `*.yaml` files in repo root or `examples/` must be valid.
- Invalid configs should fail fast with a clear error message referencing the file and step.

### Observability
- Tag pipelines with `labels: {project: "xyz", team: "ml"}`.
- Enable `metrics: true` to emit Prometheus counters automatically.
- Enable `tracing: true` for OpenTelemetry spans.

### Environment Overrides
- Allow `${ENV_VAR}` interpolation in YAML params.
- Default values via `${ENV_VAR:-default}`.
- Secrets must NOT appear in YAML; reference env vars only.

### File Naming
- `pipeline_*.yaml` or `*_pipeline.yaml` in repo root.
- Example configs in `examples/`.

## Anti‑Patterns
- Do not embed SQL strings in YAML.
- Do not use absolute paths in committed YAML (use `${PWD}` or env vars).
- Do not hardcode API keys or tokens in YAML.
