# AutoPipe Architecture

**Status of this document:** describes the system as it is at revision
`57db8694032c402ee97e479fe0a84c4f7165cb3e` and after the canonical-execution
milestone. Implemented and verified behavior is marked; proposed work is marked
and never presented as existing.

Companion documents:

- `EXECUTION_MODEL.md` — the one execution semantic
- `RUN_STATE_MACHINE.md` — lifecycle vocabulary and legal transitions
- `ARCHITECTURAL_INVARIANTS.md` — the rules and their enforcement
- `FAILURE_MODEL.md` — how failures propagate and recover
- `PROVENANCE_MODEL.md` — what each run records about itself
- `WS_CONTRACT.md` — WebSocket envelope, channels, event table

---

## The system

Two surfaces, one engine:

```
                    AUTOPIPE
                       |
              ┌────────┴────────┐
              |                 |
        CONTROL PLANE      EXECUTION PLANE
              |                 |
   CLI · library API · UI   autopipe.core.execution.ExecutionEngine
              |                 |
              └───────┬─────────┘
                      |
              Run Coordinator            app/executor/runner.py
                      |                  (thin: loads, contains, finalizes)
                Persistence
                      |
          ┌───────────┼───────────┐
          |           |           |
        Runs       Metrics     Artifacts
```

The control plane never implements execution. It describes *what* to run
(`PipelineConfig`); the execution plane decides *how*, once, in
`ExecutionEngine`.

## Components

| Component | Path | Responsibility |
|---|---|---|
| Canonical engine | `autopipe/core/execution.py` | plan → bind → invoke → propagate; terminal result; events |
| Lifecycle state machine | `autopipe/core/run_state.py` | state vocabulary, legal transitions, single mutation gate |
| Pipeline/DAG | `autopipe/core/pipeline.py` | step container + topological order; `run()` delegates to the engine |
| YAML contract | `autopipe/core/loader.py` + `autopipe/schemas/models.py` | validated config → steps; **allowlist** on importable step types |
| Step library | `autopipe/steps/`, `autopipe/monitoring/` | data, training, CV, evaluation, explainability, drift |
| Model registry | `autopipe/registry/` | versioned artifacts, sha256, atomic index |
| CLI / REPL | `autopipe/cli.py`, `autopipe/repl.py` | user entry points |
| Dashboard API | `autopipe/dashboard/backend/app/` | FastAPI, JWT, 13 routers |
| Run coordinator | `.../app/executor/runner.py` | thread, containment, guaranteed finalization |
| Projection | `.../app/executor/sink.py` | events → rows + WebSocket; **single** state writer |
| Dashboard UI | `autopipe/dashboard/frontend/` | React SPA over the API |

## Data flow for a dashboard-triggered run

```
POST /api/v1/pipelines/{id}/runs
  → validate pipeline exists, allocate run_number
  → INSERT Run (PENDING)                                  [async session]
  → BackgroundTasks: execute_run
      → thread "pipeline-run-<id>"  (≤ MAX_CONCURRENT_RUNS=4)
      → load config through the core loader (allowlist)
      → ExecutionEngine.execute(pipeline, ExecutionContext)
            emits RUN_STARTED(step_types, execution_order)
            per step: STEP_STARTED → run(**resolved_inputs) → STEP_FINISHED
            emits RUN_FINISHED(terminal state, metrics)
      → RunEventSink projects events into rows + WebSocket
      → runner._finalize guarantees the terminal write (invariant I11)
```

The CLI/library path is the same engine with a `NullEventSink`: no persistence,
exceptions re-raised to preserve the historical API contract.

## Architectural boundaries

1. **`Step` (fan-in 12)** — the interface every step and both surfaces share.
2. **The loader allowlist** — the security boundary between untrusted config and
   importable code (`TRUSTED_STEP_ROOTS`).
3. **Engine ↔ sink** — execution never persists; persistence never executes.
4. **`RunStateStore`** — the single writer of lifecycle state.
5. **Async API / sync worker** — two engines over one database; both apply the
   same SQLite pragmas.

## Deliberate non-goals (for now)

- No distributed workers, external queues, or multi-process coordination. The
  Tier 8 work is explicitly deferred until the single-process semantics are
  correct and proven.
- Provenance (Tier 4) is implemented for config hash + `Run.provenance`
  (engine_version, origin, environment, code_revision, top-level seeds,
  dataset inputs on the DataLoader path, run-path artifact registration;
  `PROVENANCE_MODEL.md`, tests in `backend/tests/test_run_provenance.py`
  and `backend/tests/test_dataset_provenance.py`).
  Step-level seed visibility and non-DataLoader data provenance are still
  not captured — listed as gaps, not fabricated.
- Request-body size is enforced by `RequestSizeLimitMiddleware`
  (`app/core/body_limit.py`, invariant I18); the old `max_request_body`
  FastAPI no-op is gone.
