# Changelog

All notable changes to AutoPipe are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

## [0.1.0] — 2025-04

Initial development release. Core DAG engine, ML/DL step library, model
registry, drift detection, LLM clients, CLI/REPL, promptfoo eval harness,
FastAPI dashboard backend and React frontend.

[Unreleased]: https://github.com/autopipe/autopipe/compare/0.1.0...HEAD
[0.1.0]: https://github.com/autopipe/autopipe/releases/tag/0.1.0
