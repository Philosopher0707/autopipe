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
- [ ] Preprocessing fit/transform + named step input bindings (kill
      leakage-by-construction)
- [ ] Drift statistics rewrite (decile PSI ±inf edges, BH correction,
      aggregation across methods, ECE bins)
- [ ] Registry hardening (locks, atomic index writes, joblib+sha256,
      uuid4 ids, torch weights_only)
- [ ] Executor hardening (bounded concurrency, per-run loggers, orphan
      sweep, in-step cancellation)
- [ ] Alembic migrations + unique constraints + indexes + SQLite pragmas
- [ ] Typing truth: strict mypy passes on core/ (gate enforced, advisory
      flag removed)

## P3 — Safety
- [x] Step-type allowlist in loader (no arbitrary imports from YAML)
- [ ] REPL evaluator isolated or disabled by default; secret redaction in
      history/config display
- [ ] Pin promptfoo version; single credential path with masking

## P4 — Product honesty
- [x] pi_coding + REPL behind optional extras (removed from top-level exports; explicit imports only; modules marked non-core)
- [x] Distributed tuning honest or deleted (deleted: zero consumers, K8s result collection was NotImplementedError, Hyperband formula wrong)
- [ ] 0.2.0 release: version bump, changelog, tagged build
