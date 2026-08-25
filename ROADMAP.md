# AutoPipe Remediation Roadmap

Execution tracker for bringing the codebase to a truthful, world-class
state. Every phase lands as verified commits with green suites.

## P0 — Truth & hygiene
- [x] Purge 1,764 tracked tool-residue files; ignore classes going forward
- [x] Consolidate test trees under `tests/` (single collected suite)
- [x] Fix CI: pytest-timeout dep, integration on PRs, backend + frontend-lint jobs
- [x] Single formatter (ruff-format), zero ruff violations, gitleaks pre-commit
- [x] Python floor 3.10 (3.9 was broken despite classifier)
- [x] README truth rewrite; CONTRIBUTING.md; CHANGELOG.md; stale docs removed
- [x] De-fabricate endpoints (`simulate` default off; honest empties/501s)

## P1 — Make it true
- [x] Fix import/instantiation showstoppers (`tracking`, `experiments`,
      `OptunaSearchStep.execute→run`, evaluation classes not Steps)
- [x] Assign `step.output` in run loop; unify Step contract
- [x] One validation/loading path (pydantic schemas + shared alias map;
      `autopipe create` output must pass `autopipe validate`)
- [x] Backend auth for real: router-level deps, role gates, no admin
      self-registration, WS handshake tokens, persistent SECRET_KEY

## P2 — Correctness
- [x] Preprocessing fit/transform + named step input bindings (kill
      leakage-by-construction)
- [x] Drift statistics rewrite (decile PSI ±inf edges, BH correction,
      aggregation across methods, ECE bins)
- [x] Registry hardening (locks, atomic index writes, joblib+sha256,
      uuid4 ids, torch weights_only)
- [x] Executor hardening (bounded concurrency, per-run ContextVar log
      isolation, startup orphan sweep, in-step cancellation)
- [x] UniqueConstraint(model_id, version), FK indexes, SQLite pragmas
      (foreign_keys/WAL/busy_timeout)
- [ ] Alembic migration env for existing deployments (fresh installs use
      create_all; constraint/index changes above are additive)
- [x] Typing truth: strict mypy passes on core/ (gate enforced, advisory
      flag removed)

## P3 — Safety
- [x] Step-type allowlist in loader (no arbitrary imports from YAML)
- [x] REPL: .format() sandbox escape blocked, unknown-command eval
      fallthrough removed, secrets redacted in config/history display
- [x] Pin promptfoo version; single credential path with masking

## P4 — Product honesty
- [x] pi_coding + REPL behind optional extras (removed from top-level exports; explicit imports only; modules marked non-core)
- [x] Distributed tuning honest or deleted (deleted: zero consumers, K8s result collection was NotImplementedError, Hyperband formula wrong)
- [ ] 0.2.0 release: version bump, changelog, tagged build
