# CONTEXT — AutoPipe autonomous engineering mission

> Compact anchor for resuming work with a small context window. Re-read this
> first. Full mission spec: the original prompt. Full architecture rationale:
> `AUTOPIPE_NORTH_STAR.md`. Enforcement status: `docs/architecture/*.md`.

## Baseline & current state

- Mission baseline revision: `57db8694`. HEAD: `12efe880`.
- Evidence labels follow NORTH_STAR (OBSERVED / SOURCE-DERIVED / …).

### DONE (verified by tests)

- **M1 rate-limit wiring (I18) — `08e7f43b`:** default limiter on ALL HTTP
  routes (was: only /auth despite comment claiming data routes); `_rl`
  dependency runs before auth; `X-RateLimit-*` on every response via
  `RateLimitHeadersMiddleware`; 429 has `Retry-After`+headers; CORS exposes
  them; autouse limiter reset in backend conftest.
  Tests: `backend/tests/test_rate_limit_headers.py` (6, production-wiring).
- **M2 whole-repo ruff — `4d52d740`:** `ruff check/format .` fully clean;
  examples get structural E402 ignore (sys.path bootstrap).
- **One execution semantic (I1–I4):** duplicate dashboard loop deleted;
  `autopipe/core/execution.py::ExecutionEngine` is canonical. Dashboard
  executor (`app/executor/runner.py`) delegates to it.
  Tests: `tests/unit/core/test_execution_engine.py`,
  `backend/tests/test_executor_integration.py`.
- **Run state machine (I5–I7):** `autopipe/core/run_state.py` gate +
  CAS writes; `RunStateStore` single writer; API PATCH → 409 on illegal
  transitions; terminal states immutable w/ `allow_recovery`.
- **Failure containment (I11–I12):** every worker path caught → FAILED;
  startup orphan sweep; graceful shutdown. `2cbb2cbe`, `9aa9f64d`.
- **Validation = execution readiness (I8–I10):** loader does plan/binding/
  unknown-key checks at load; shipped examples execute
  (`tests/unit/test_shipped_examples_execute.py`).
- **One shared DB** for API + executor in tests; admission gate (no Run row
  for unrunnable config); run config provenance + race-safe run numbering.
- **PiCoding config bypass closed (I16) — `7144a6fb`:**
  `QUARANTINED_STEP_MODULES` enforced in `import_class` (single choke
  point: CLI/YAML/admission/executor); FQ-name path was the hole.
  Tests: `tests/unit/core/test_loader.py::TestQuarantinedStepBoundary`.
- **Drift producer bridge — `665ff239`:** `RunStateStore.record_drift`
  persists detector outputs (incl. nested `DriftDashboardStep` batch) into
  `DriftReport`+`DriftAlert` in `runner._finalize` before terminal write;
  failure contained (I11). Tests: `backend/tests/test_executor.py`.
- **WS contract unified — `f998ea0c`:** every broadcast is the envelope
  `{type,data,timestamp}` (payload only in `data`); frontend `WSEventType`
  matches emitted events; `parseWSMessage` guards malformed frames. Contract:
  `docs/architecture/WS_CONTRACT.md`.
  Tests: `backend/tests/test_websocket_contract.py` (5), frontend
  `websocket.test.ts` parse guards (3).
- **Dead user API-key path removed — `2fa61352`:** `users.api_key` column
  dropped (migration `f2a9c1d4e7b8`), `Config.get_llm_config` + the four
  `Config.*_API_KEY` attrs deleted; absence tests at both layers.
- **I12 credential reference model — `02e1fc22` + impl:** design doc
  `docs/architecture/CREDENTIAL_REFERENCE_MODEL.md` (I12-A…I12-I, T0–T10,
  threat model, self-review) written before code; `PipelineConfig` now
  rejects secret-shaped step params via `SecretMaterialError` (single
  choke: CLI/YAML/library/admission); `LLMProviderConfig.api_key` slot
  removed; CredentialManager docstring corrected to env-only; invariants
  doc I20 added. Sentinel tests: env key never appears in provenance or
  the SQLite file bytes; 400 bodies never echo the rejected value.
- **I12-H log/failure-boundary witness:** env sentinel enters the real
  credential path; offline Ollama failure exercises real engine
  serialization; sentinel absent from caplog(DEBUG, all loggers),
  stdout/stderr, error/traceback, every event field, `repr()` of
  result/client/exception, durable `error_message`, and SQLite bytes
  (success + failure paths). Ceilings: third-party SDK/CLI loggers with
  live keys; operator-step self-emission (out of trust); live WS capture
  (proxy-verified — payload = same `error` string as the DB column).
  Tests: `tests/unit/test_secret_log_boundary.py`,
  `backend/tests/test_run_provenance.py`.
- Security milestones: JWT on all data routes, loader step allowlist,
  pinned promptfoo, REPL/pi_coding quarantined, trusted hosts, body limit,
  secret-key startup policy, rate limiter keyed by peer unless
  TRUST_PROXY_HEADERS.

### KNOWN GAPS (not yet started)

- `examples/example_pipeline.py` needs OPENROUTER_API_KEY to execute
  (credential-gated; validate-only in invariant test — acceptable).
- Live `drift.alert` WS push has no subscriber (contract documented;
  polling is the read path).
- File `artifacts` table has `sha256` column but no writer (NULL =
  not recorded; PROVENANCE_MODEL gap).

## Quality gates (run before every commit)

```bash
ruff check . && ruff format --check . && mypy autopipe/core             # whole-repo lint/format + strict engine
PYTHONPATH=. pytest tests -q                                            # 311 pass expected
autopipe/dashboard/backend/.venv/bin/python -m pytest autopipe/dashboard/backend/tests -q  # 177 pass expected
cd autopipe/dashboard/frontend && pnpm typecheck && pnpm test           # 43 pass expected
```

Note: bare `pytest` fails in this shell (conda `litllm` env lacks the
installed package) — use `PYTHONPATH=.` as above.

## Architecture map (minimal)

- `autopipe/core/` — engine: `execution.py` (canonical engine),
  `run_state.py` (transition gate), `pipeline.py`, `loader.py`, `step.py`.
- `autopipe/dashboard/backend/app/executor/` — `runner.py` (coordinator,
  daemon workers, sweep), `sink.py` (RunStateStore = sole DB writer),
  `admission.py`, `registry.py`.
- `app/api/v1/router.py` — JWT (`_auth`) + rate-limit deps per router.
- `app/core/security.py` — SimpleRateLimiter (module-global `_rate_limiter`).
- `app/api/v1/endpoints/websocket.py` — WS auth + `_envelope` broadcasts
  (contract: `docs/architecture/WS_CONTRACT.md`).
- `docs/architecture/` — ARCHITECTURE, ARCHITECTURAL_INVARIANTS (I1–I18,
  status-labelled), EXECUTION_MODEL, RUN_STATE_MACHINE, FAILURE_MODEL,
  PROVENANCE_MODEL, WS_CONTRACT. Keep these truthful when behavior changes.

## Priority queue (status)

| # | Item | Status |
|---|------|--------|
| 1 | Rate-limit wiring + headers + I18 test | DONE `08e7f43b` |
| 2 | Whole-repo ruff clean (examples/, test_simple.py) | DONE `4d52d740` |
| 3 | WS auth parity + RunDetail token (I17) | DONE `6bdb5c08` |
| 4 | Provenance: env/code/seed snapshot on Run (PROVENANCE_MODEL gap) | DONE `c240f604` (Run.provenance JSON + migration `3e7a9c4d1f62`; I14/I15 VERIFIED) |
| 5 | MetricLog writer: nothing in executor writes metric series | DONE (mark_step inserts MetricLog rows in CAS txn; 155 backend tests) |
| 6 | Artifact content-addressing in dashboard ORM | DONE (ChartArtifact.sha256 hook + artifacts.sha256 col; migration `8b5d2e1a7c34`; 156 backend tests) |
| 7 | Drift producer bridge (core DriftReport → durable row) | DONE `665ff239` (record_drift in _finalize; nested batch + failure-injection tests; 166 backend tests) |
| 8 | LLM: drop SDK global-key mutation (I12) | DONE (`openai.OpenAI(api_key=…)` instance-scoped; timeout popped from JSON body on Ollama/OpenRouter; tests `tests/unit/test_llm_client.py`) |
| 9 | Legacy SHA256 password migration/removal path | DONE (upgrade-on-login both form+JSON tested; `count_legacy_password_hashes` = removal gate: delete `_legacy_hash_password` + non-`$` branch when it returns 0) |
| 10 | Frontend WS contract fixes (RunDetail token/shape) | DONE `f998ea0c` (envelope unified both sides; WS_CONTRACT.md) |
| 11 | PiCoding config-driven admission bypass (I16) | DONE `7144a6fb` (QUARANTINED_STEP_MODULES in import_class) |
| 12 | WS handshake rate limiting (D3 closure) | DONE (`check_websocket_rate_limit`, shared peer bucket, close 1013; `test_ws_rate_limit.py`) |
| 13 | Dead user-API-key path removal (users.api_key + get_llm_config) | DONE `2fa61352` (migration `f2a9c1d4e7b8`; 310 repo / 176 backend tests) |
| 14 | I12 key-reference indirection — design first, then enforce | DONE (`02e1fc22` design + impl: secret-param deny at PipelineConfig, I20, sentinel tests; ceilings: T-G value-shape) |
| 15 | I12-H runtime secret → log boundary witness | DONE (real-path witness `tests/unit/test_secret_log_boundary.py` + failure-path DB grep; caplog/capsys/events/traceback/repr channels clean; ceilings: third-party SDK loggers, operator-step self-emission) |

## Decisions log

- D1: Rate limit runs BEFORE auth in dependency order so 401-hammering also
  counts against the limiter.
- D2: /auth keeps default limit too (comment's "double-count" rationale was
  bogus: separate identifiers = separate buckets; excluding it left /auth/me
  unlimited).
- D3: websocket router now IS rate-limited (closed): handshakes share the
  per-peer default bucket; FastAPI 0.109 won't inject Request into WS-route
  deps, so `check_websocket_rate_limit` keys on the WebSocket (same
  headers/client/state) and refuses with close 1013 (no 429 on a handshake;
  raising HTTPException there hangs the handshake — observed).
- D4: tests must exercise production wiring (real app, real limiter) —
  autouse limiter reset in backend conftest prevents cross-test 429s.
- D5: examples/*.py structural E402 ignored (sys.path bootstrap before
  local-package import); everything else whole-repo ruff-clean.
- D6: WS auth = JWT decode + DB active-user lookup (REST parity); token
  attached centrally in WebSocketClient.connect, bare URL stored for
  reconnect freshness.
- D7: Run provenance is one JSON column (`Run.provenance`), not five scalar
  columns — additive migrations stay cheap; NULL = not recorded, and
  code_revision uses the explicit string "unavailable" per PROVENANCE_MODEL
  non-goal.
- D8: WS messages use the envelope `{type,data,timestamp}` only — payload
  fields live in `data`; routing is server-side; clients dispatch on
  `type`. No flat legacy shapes kept "for compatibility" (single consumer,
  same repo).
- D9: `record_drift` collects batches with a depth-limited dict walk
  (depth 3), not a flat scan — covers `DriftDashboardStep`'s nested
  `feature_drift` output; single caller in `_finalize` makes duplicate
  writes impossible by construction (no dedup key).

## Resume procedure

1. `git status` / `git diff` — know the working tree.
2. Run the quality gates above.
3. Read `docs/architecture/ARCHITECTURAL_INVARIANTS.md` for what's VERIFIED.
4. Pick top pending queue item; loop: baseline test → implement → unit +
   integration + failure-injection → gates → update this file + docs →
   commit → reassess.
