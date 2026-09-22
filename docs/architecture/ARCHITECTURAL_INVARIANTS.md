# Architectural Invariants

Each invariant records its current state with one label: **VERIFIED** (enforced
by a passing test), **IMPLEMENTED** (enforced by code; test coverage noted), or
**PROPOSED** (not yet true). Nothing here claims a behavior the code does not
have.

Baseline revision for this version: `57db8694032c402ee97e479fe0a84c4f7165cb3e`.

---

## Execution

### I1 — Every execution path uses the canonical execution engine.
- **Definition:** Dependency resolution, input binding, output propagation, step
  lifecycle, cancellation and terminal-state selection are implemented exactly
  once, in `autopipe.core.execution.ExecutionEngine`.
- **Owner:** `autopipe/core/execution.py`.
- **Enforcement:** `Pipeline.run` delegates to the engine; the dashboard
  coordinator delegates to it (`app/executor/runner.py`). The duplicate loop that
  used to live in the executor was deleted.
- **Test:** `tests/unit/core/test_execution_engine.py`;
  `backend/tests/test_executor_integration.py::test_named_bindings_are_honored_through_the_real_wiring`.
- **Failure mode if violated:** two meanings of "run a pipeline" that disagree —
  the original defect this milestone removed.
- **Status:** VERIFIED.

### I2 — Input binding semantics are identical everywhere.
- **Definition:** `resolve_step_inputs` is the only implementation of the
  precedence rule *named bindings → depends_on → initial_inputs*.
- **Owner:** `autopipe/core/execution.py::resolve_step_inputs`.
- **Test:** `TestBindingSemantics`,
  `test_resolve_step_inputs_is_the_single_implementation`.
- **Failure mode:** a step receives `{step_name: value}` in one runner and
  `{param: value}` in another (the original dual-semantics bug).
- **Status:** VERIFIED.

### I3 — Step output semantics are identical everywhere.
- **Definition:** `step.output` is assigned by the engine on every successful
  step, and only the engine assigns it.
- **Owner:** `ExecutionEngine._run_step`.
- **Test:** `test_success_assigns_step_output_attribute`.
- **Status:** VERIFIED.

### I4 — Execution lifecycle has one authoritative owner.
- **Definition:** A run's execution begins and ends inside
  `ExecutionEngine.execute`; no other code decides the lifecycle.
- **Owner:** `autopipe/core/execution.py`.
- **Enforcement:** the engine returns a terminal `ExecutionResult`; the
  dashboard's `RunStateStore` only *persists* the states the engine selects.
- **Test:** `TestLifecycle` (terminal-state selection), `TestContainment`.
- **Status:** VERIFIED.

---

## Persistence

### I5 — Run/step state has one authoritative mutation path.
- **Definition:** Every persisted lifecycle write goes through
  `autopipe.core.run_state.ensure_transition`. The dashboard's `RunStateStore`
  is the single writer of run/step rows; the API's PATCH handler validates
  through the same gate.
- **Owner:** `autopipe/core/run_state.py` (gate) +
  `app/executor/sink.py::RunStateStore` (writer).
- **Enforcement:** `ensure_transition` raises `StateTransitionError` for an
  illegal move; the API converts it to HTTP 409.
- **Test:** `tests/unit/core/test_run_state.py` (43 cases);
  `backend/tests/test_runs.py::test_cannot_resurrect_a_terminal_run`.
- **Failure mode:** a finished run silently resurrected, or a corrupt state
  accepted as "no prior state".
- **Status:** VERIFIED.

### I6 — Terminal run states cannot silently regress.
- **Definition:** `SUCCESS`/`FAILED`/`CANCELLED` have an empty transition set;
  leaving one requires an explicit `allow_recovery=True` override.
- **Owner:** `autopipe/core/run_state.py`.
- **Enforcement:** `TERMINAL_RUN_STATES` plus the override parameter, which is
  greppable at every call site.
- **Test:** `TestTerminalImmutability` (parametrized over all terminal states
  and all targets).
- **Status:** VERIFIED.

### I7 — Database writes use the intended transaction boundary.
- **Definition:** The executor's sync engine applies the same SQLite hardening
  (`foreign_keys=ON`, `busy_timeout=5000`, `WAL`) as the async API engine, and
  each logical write commits as a unit.
- **Owner:** `app/executor/runner.py::_configure_sqlite`, `app/executor/sink.py`.
- **Enforcement:** pragmas applied on connect to *both* engines.
- **Failure mode:** the writer path running with weaker integrity than the
  reader path (the original asymmetry).
- **Status:** IMPLEMENTED. The executor still uses a *separate* sync engine —
  necessary because threads cannot share async sessions — but the wiring
  integration tests use one shared database for both halves. Remaining Tier 1
  work: make the engine choice a single injectable decision.

### I19 — No Run is created for a configuration that cannot run, and a rejected
request persists nothing.
- **Definition:** A Run is created only for a configuration admitted through the
  single admission gate, and if admission passes the Run **is** dispatched.
  Conversely, an error response must not leave persisted side effects.
- **Owner:** `app/executor/admission.py::admit_run_config`.
- **Enforcement:** `POST /pipelines/{id}/runs` and
  `POST /experiments/{id}/trials` both admit *before* inserting anything.
  The old code created the Run unconditionally and dispatched it only when the
  config happened to contain a `"steps"` key (two inconsistent notions of
  "runnable"), and the trials endpoint committed its runs before rejecting
  `simulate=true`, leaving orphaned PENDING runs behind.
- **Test:** `backend/tests/test_run_admission.py` — an unbuildable override is a
  400 *and* persists no Run; a pipeline with no config is a 400; the 501
  simulate rejection persists no Runs; admitted trials create exactly `n_trials`.
- **Failure mode:** a Run that nothing will ever execute, permanently PENDING —
  which also violates I12.
- **Status:** VERIFIED.

---

## Reliability

### I11 — No worker exception can strand a Run.
- **Definition:** An exception anywhere in the worker thread — inside the engine,
  the sink, or the finalization write — is contained and the run reaches a
  terminal state.
- **Owner:** `app/executor/runner.py::_run_pipeline_in_thread` (containment) +
  `ExecutionEngine.execute` (never raises).
- **Enforcement:** the engine converts any escaping exception into a FAILED
  result; the coordinator's `finally` always finalizes, and a last-resort
  `_force_terminal` runs if finalization itself fails.
- **Test:** `test_engine_never_raises_when_a_step_raises_base_exception`;
  `test_post_processing_failure_still_returns_terminal`;
  `backend/tests/test_executor_integration.py::test_failing_step_is_failed_not_stranded`;
  `backend/tests/test_executor.py::test_prologue_register_failure_still_forces_terminal`;
  `backend/tests/test_executor.py::test_sink_close_failure_still_finalizes`;
  `backend/tests/test_executor.py::test_finalize_failure_forces_terminal`;
  `backend/tests/test_executor.py::test_shutdown_executor_cancels_and_sweeps`.
- **Failure mode:** exception → daemon thread dies → Run claims RUNNING forever
  with no error and no event. This was reproducible at baseline and is now
  closed (backend suite: 28 swallowed thread exceptions → 0).
- **Status:** VERIFIED.

### I12 — Every Run reaches a terminal state.
- **Definition:** For any execution, the result's state is terminal and a
  terminal write is attempted.
- **Owner:** `ExecutionEngine.execute` + `runner._finalize`.
- **Test:** `test_engine_reaches_a_terminal_state_for_every_outcome`;
  `backend/tests/test_executor.py::test_cancel_before_register_is_honoured`
  (pending-cancel queue: a cancel before `register_run` still ends CANCELLED).
- **Status:** VERIFIED.

### I13 — Cancellation is observable.
- **Definition:** Cancelling a run yields a `CANCELLED` terminal state and a
  `STEP_SKIPPED` event with a reason for every not-started step.
- **Owner:** `ExecutionEngine` + `CancellationToken`.
- **Enforcement:** the registry's `threading.Event` *is* the engine token's
  event, so a PATCH cancellation reaches the engine without a second flag.
- **Test:** `TestCancellation`;
  `backend/tests/test_executor.py::test_run_pipeline_in_thread_cancellation`.
- **Status:** VERIFIED.

---

## Validation

### I8 — VALID means execution-ready.
- **Definition:** `autopipe validate` never reports VALID for a pipeline that
  cannot be instantiated and executed.
- **Owner:** `autopipe/cli.py` (`validate`) + `autopipe/core/loader.py`.
- **Enforcement:** `validate` builds the pipeline through
  `load_executable_pipeline` — the core's definition of execution readiness —
  which resolves step types through the allowlist, constructs the steps, and
  **resolves the execution plan**. That last part matters: a dependency cycle is
  schema-valid and buildable, so only plan resolution catches it. The previous
  implementation checked *importability* alone, which is why it reported VALID
  for three shipped examples that could not be constructed.
- **Test:** `tests/unit/test_shipped_examples_execute.py`
  (`test_validate_rejects_a_config_that_cannot_be_constructed`,
  `test_validate_rejects_a_cyclic_dependency_graph`,
  `test_load_executable_pipeline_catches_what_the_schema_does_not`,
  `test_schema_validation_alone_is_not_execution_readiness`).
- **Failure mode:** a user is told their config is fine and it then fails to run.
- **Status:** VERIFIED.

### I9 — Every accepted step type is constructible, and every shipped config is.
- **Definition:** Every step class reachable from YAML can be instantiated with
  the parameters the loader accepts, and every config the repository ships loads.
- **Owner:** `autopipe/core/loader.py` (alias map + allowlist).
- **Enforcement:** `test_shipped_examples_execute.py` loads every file in
  `examples/` and the template emitted by `autopipe create`;
  `test_step_alias_coverage.py` requires every public `Step` subclass to be
  addressable from YAML.
- **Note:** the `sample_data_loader` alias was added for the bundled
  scikit-learn sample loader, which **removed** the last `ALIAS_EXEMPT` entry
  other than the quarantined `PiCodingStep`.
- **Status:** VERIFIED.

### I10 — Every accepted binding resolves.
- **Status:** IMPLEMENTED — dangling bindings fail loudly (load-time via
  `PipelineConfig`, run-time via `InputBindingError`;
  `test_unresolvable_binding_fails_the_run_with_a_typed_error`), and the shipped
  examples now exercise named bindings.

---

## Provenance (Tier 4)

### I14 — Results have provenance. / I15 — Missing provenance is explicit.
- **Status:** PROPOSED. `ExecutionResult.engine_version` and
  `ExecutionContext.metadata` are the anchor points; durable provenance columns
  are not yet implemented. Per the no-fabricated-data rule, nothing is invented.

---

## Security

### I16 — Untrusted configuration cannot escape the allowed execution surface.
- **Definition:** Step types resolve under `TRUSTED_STEP_ROOTS`.
- **Owner:** `autopipe/core/loader.py`.
- **Test:** `tests/unit/core/test_loader.py`.
- **Status:** VERIFIED (unchanged by this milestone).

### I17 — Authentication and authorization are explicit.
- **Status:** VERIFIED (unchanged): router-level JWT, role gates on destructive
  routes, WS token handshake.

### I18 — Security controls claimed by configuration actually execute.
- **Status:** **PROPOSED — violated at baseline.** The documented
  `max_request_body` limit is a silent no-op (FastAPI stores it in `self.extra`
  and never applies it). Fixing this is a Tier 5 item.
