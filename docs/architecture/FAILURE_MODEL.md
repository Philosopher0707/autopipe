# Failure Model

**Status:** IMPLEMENTED and VERIFIED for the execution path (this milestone).
Remaining gaps are listed explicitly at the end.

## Containment chain

Every failure on the execution path is handled at the lowest level that can
still produce a correct outcome, and is never silently dropped.

| Failure | Detected by | Handled by | Run ends as | User-visible |
|---|---|---|---|---|
| Step raises `Exception` | `ExecutionEngine._run_step` | outcome recorded as `FAILED`; downstream steps `SKIPPED` | `FAILED` | `error_message` = `Step '<name>' failed: <Type>: <msg>` |
| Step raises `BaseException` | same | same — the engine catches `BaseException` | `FAILED` | same |
| Step cooperatively cancels | `CancellationError` | outcome `SKIPPED`, reason `cancelled_in_step` | `CANCELLED` | no error (cancellation is not an error) |
| Invalid dependency graph | `_resolve_order` | `plan_resolved: False` event; no step executes | `FAILED` | error message from the resolution failure |
| Dangling named binding | `resolve_step_inputs` | `InputBindingError`; step `FAILED` | `FAILED` | names the missing upstream step |
| Config cannot be loaded | `runner._execute` | synthetic `RUN_STARTED(plan_resolved=False)` + FAILED result | `FAILED` | `Pipeline load error: …` |
| Visualization raises | `_visualize_step` | logged WARNING + `VISUALIZATION_FAILED` event; **run continues** | unchanged | warning in the run log stream |
| Event sink raises | `_EventBus.emit` | recorded in `result.sink_errors`, logged WARNING | unchanged (execution is not observability's hostage) | logged; surfaced by `_finalize` |
| DB write fails during execution | `RunEventSink` → engine | sink error recorded; execution continues | unchanged | logged |
| Finalization write fails | `runner._finalize` | `_force_terminal` retries `FAILED` | `FAILED` | CRITICAL log if even that fails |
| Sink `close()` raises | `runner._run_pipeline_in_thread` finally | logged CRITICAL; finalization still runs independently | unchanged (by close) | CRITICAL log |
| Prologue (`register_run`, store) raises | same containment try | `_force_terminal` (when a store exists) | `FAILED` | CRITICAL log |
| Post-processing raises | `ExecutionEngine.execute` outer try | forced FAILED result + `RUN_FINISHED` emitted | `FAILED` | error on the result |
| Process crash mid-run | startup `sweep_orphaned_runs` | `RUNNING → FAILED` (legal transition), steps `FAILED` | `FAILED` | "Interrupted by server restart" |
| Graceful shutdown | `runner.shutdown_executor` | cancel active runs, join live threads, sweep leftovers | terminal | stop handler runs before DB close |
| Cancellation requested | `CancellationToken` | remaining steps `SKIPPED` with reason | `CANCELLED` | step states + reason |
| Illegal state transition attempted | `ensure_transition` | raises `StateTransitionError`; API → **409** | unchanged | 409 with the transition and context |

## The rule behind the table

> **An exception may change the outcome; it may never erase the record of it.**

Concretely:

- the engine never propagates (invariant I11), so a daemon thread cannot die
  with a run still claiming `RUNNING`;
- a broken observer cannot decide execution, but its failure is *recorded*
  (`result.sink_errors`) rather than swallowed;
- terminal states cannot be silently rewritten (invariant I6);
- the only path that ends a run's life is `runner._finalize`, and it has a
  fallback (`_force_terminal`) whose own failure is logged at CRITICAL.

## Verified at baseline vs now

| Symptom | Baseline | Now |
|---|---|---|
| Worker thread exceptions swallowed as pytest warnings | 28 | **0** |
| Runs left non-terminal after an infrastructure failure | yes (reproducible by injection) | **no** (`test_failing_step_is_failed_not_stranded`) |
| `RUNNING` runs recoverable only by a restart sweep | yes | still the crash-recovery path, but no longer reachable by ordinary in-process failures |

## Remaining gaps (explicit, not solved)

1. **Broadcast delivery is best-effort.** If the event loop is gone, WebSocket
   updates are skipped (logged). Correctness is unaffected; *timeliness* of the
   UI is. Not yet measured or alerted on.
2. **No retry semantics.** A failed step is not retried. `tenacity` is a
   dependency but no execution-level retry policy exists. Tier 6.
3. **Graceful shutdown joins with a timeout** (`shutdown_executor`, default
   5 s). A step that ignores cancellation past the deadline is swept to FAILED
   by the same call; no drain-forever option. Tier 6.
4. **Partial failure of a *multi-run* batch** (e.g. `POST /experiments/{id}/trials`)
   is not transactional: some trials may start while others fail. Tier 6.
5. **SQLite contention** under concurrent writers relies on `busy_timeout`
   (5 s) on both engines. Behavior under sustained contention is not measured.
