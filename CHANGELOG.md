# Changelog

All notable changes to AutoPipe are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Known gaps (tracked in ROADMAP)

- Alembic migration env for pre-0.2.0 deployments (fresh installs use
  `create_all`; 0.2.0's constraint/index changes are additive).

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
