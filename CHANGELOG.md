# Changelog

All notable changes to AutoPipe are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Rate-limit headers on every HTTP response (`X-RateLimit-Limit`,
  `X-RateLimit-Remaining`; 429 also sends `Retry-After`), exposed via CORS.
  The default limiter now covers **all** routes (previously only `/auth`
  despite a comment claiming otherwise), runs before auth, and resets per
  test via an autouse fixture.
- WebSocket auth parity with REST (I17): `authenticate_websocket` now checks
  the token subject against the DB (existing + active user), rejecting
  deleted/deactivated users the way REST already did. The frontend attaches
  the access token centrally in `wsClient.connect()`, fixing RunDetail's
  run-scoped WS URL, which connected without a token and was closed 1008.

- Run provenance: `Pipeline.config_hash` and `Run.config_hash` now store a
  sha256 of the canonical JSON config (key order independent). The pipeline
  hash is maintained by a `validates("config")` hook; the run hash is written
  once at insert and describes that run's own config copy. Pre-existing rows
  keep NULL ("not recorded").
- `Run.provenance` JSON snapshot at creation on every path (dashboard
  trigger, experiment trials, demo seed): engine version, origin, environment
  fingerprint (python/platform/package versions), git `code_revision`
  (`-dirty` aware, `"unavailable"` when git cannot run), and top-level
  config `seed`/`seeds`. Historical rows keep NULL (I15, no retro-fitting).
  Alembic migration `3e7a9c4d1f62` (additive, reversible).
- Executor writes the `MetricLog` time series: numeric step metrics land as
  append-only rows (run/step/pipeline/experiment ids, `step_index` =
  order_index) inside the same transaction as the step status CAS — a
  conflict rolls the points back with it. Previously only demo seeds and a
  manual POST endpoint populated metric series, so real runs had no
  chartable trace.
- Dashboard artifacts are content-addressed: `ChartArtifact.sha256` is
  written by a `validates("data")` hook (canonical JSON sha256, same as
  `hash_config`) so identity follows content, not row id; the file
  `artifacts` table gains a `sha256` column (NULL until a writer exists —
  "not recorded", never a placeholder). Alembic migration `8b5d2e1a7c34`
  (additive, reversible).
- Unique `(pipeline_id, run_number)` on runs with a retrying allocator
  (`app/api/v1/endpoints/run_numbers.py`): concurrent triggers no longer race
  the read-max-then-insert numbering; exhaustion is an explicit 409 instead of
  a 500. Alembic migration `b7e4c2a91f03` (additive, reversible).
- Alembic migration environment for the dashboard database
  (`autopipe/dashboard/backend/migrations`). Existing create_all databases
  adopt it via `alembic stamp head`; fresh deployments use `alembic upgrade
  head`. Initial revision verified schema-identical to `Base.metadata`.
- `autopipe run --output results.json` writes step results as JSON; the
  never-implemented `--cache`, `--parallel` and `--step` flags were removed
  (they were accepted and silently ignored).
- `autopipe validate` accepts Python pipeline files (`.py`), loading them
  through the same `load_pipeline_from_module` path `run` uses. Module bodies
  execute on load, so only validate files you trust.

### Changed

- `PipelineConfig` now forbids unknown keys (`extra="forbid"`). The `env` and
  `settings` fields were removed — nothing ever read them — and `description`
  is now a real field. Shipped examples and the `autopipe create` template no
  longer emit `env:` blocks.
- Plan resolution and input-binding signature checks moved into
  `load_pipeline_from_config` itself, so every entry point (YAML, `.py`, CLI
  validate/run, dashboard run admission) rejects cycles, dangling dependencies
  and mistyped binding keys at **load** time. `load_executable_pipeline`
  remains as a compatibility alias.
- Dashboard demo seeds (`app.seed.PIPELINE_SEEDS`) are now admissible
  executable pipeline configs instead of inert metadata, guarded by an
  admission test.

## [0.2.0] — 2026-08-25

Full remediation of the audit findings, phases P0-P4. The theme is honesty:
every advertised capability now either works or is gone; every endpoint that
cannot deliver returns an explicit error instead of fabricated data.

### Remediation series (P0 — truth & hygiene)

- chore(repo): purged 1,764 tracked tool-residue files (sandbox caches, agent
  session transcripts, registry pickles, SQLite WALs); archive design docs
  moved to `docs/archive/`; example configs moved to `examples/`.
- chore(tests): consolidated all Python test trees under `tests/` so plain
  `pytest` collects the entire suite; dashboard backend tests get a dedicated
  CI job.
- ci: fixed integration job (`pytest-timeout` added and job un-gated from
  main-only), added dashboard-backend job, added frontend lint step, bumped
  codecov action, added concurrency groups and job timeouts.
- style: ruff is now the single linter AND formatter (`ruff-format` replaces
  black + isort); pre-commit revs refreshed; gitleaks secret scanning added.
- docs: README rewritten against reality; CONTRIBUTING.md and CHANGELOG.md
  added; stale TUI documentation removed.
- breaking: dropped Python 3.9 support (PEP 604 syntax in `autopipe.exceptions`
  made it unusable on 3.9 despite the classifier); floor is now 3.10.
- fix: three `F821` undefined-name bugs in `registry.export`, `tracking.base`
  and `tuning.optuna_search` annotations.

### P1 — Core engine truth

- security(backend): JWT auth enforced on every data route (was advertised,
  never applied); admin role gates on destructive routes; registration no
  longer trusts client-sent roles (first account bootstraps admin); WS
  handshakes require `?token=`; legacy SHA256 hashes upgrade to bcrypt on
  login; SECRET_KEY env-backed; token TTL cut to 24h.
- fix(core): Step contract unified (`execute()` -> `run()`), `step.output`
  actually assigned, evaluation step constructors fixed, package exports
  resolve (`test_all_exports_resolve` guards this permanently).
- fix(core): `autopipe validate` uses the same alias map as the loader and
  fails on invalid steps — `autopipe create` output now validates.

### P2 — Correctness

- fix(core): preprocessing no longer leaks — real fit()/transform()
  separation with train-statistics regression tests; transform() raises
  before fit() instead of silently passing raw data.
- feat(core): named input bindings (`inputs: {param: upstream_step}`).
- fix(monitoring): decile PSI over reference quantiles with +/-inf edges;
  Benjamini-Hochberg multiple-testing control across features; chi-square
  zero-cell handling; ECE bin alignment fixed.
- security(registry): atomic index writes (os.replace), uuid4 model ids,
  SHA-256 artifact integrity verification, joblib round-trip,
  torch.load(weights_only=True).
- security(executor): bounded run concurrency, per-run WebSocket log
  isolation via ContextVar filter, startup sweep of orphaned RUNNING rows.
- security(db): real UniqueConstraint(model_id, version), FK indexes,
  SQLite PRAGMA foreign_keys/WAL/busy_timeout.
- feat(typing): strict mypy passes on autopipe/core and is a hard CI gate.

### P3/P4 — Safety & product honesty

- security(loader): step-type allowlist — YAML configs can no longer import
  arbitrary modules (`type: os.system` was RCE).
- security(repl): closed the str.format sandbox escape; unknown commands no
  longer fall through to eval(); secrets redacted in config/history output.
- refactor(llm): all clients resolve keys through CredentialManager with
  masking (single credential path).
- security(eval): promptfoo pinned (unpinned npx ran unvetted code).
- breaking(api): PiCodingStep/REPL quarantined out of the top-level API —
  explicit imports only; both documented as non-core opt-in tools.
- breaking(tuning): DistributedSearch/KubernetesDistributedSearch deleted
  (K8s result collection was NotImplementedError, Hyperband formula wrong,
  zero consumers).

## [0.1.0] — 2025-04

Initial development release. Core DAG engine, ML/DL step library, model
registry, drift detection, LLM clients, CLI/REPL, promptfoo eval harness,
FastAPI dashboard backend and React frontend.

[Unreleased]: https://github.com/autopipe/autopipe/compare/0.1.0...HEAD
[0.1.0]: https://github.com/autopipe/autopipe/releases/tag/0.1.0
