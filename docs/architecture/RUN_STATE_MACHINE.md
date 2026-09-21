# Run State Machine

**Status:** IMPLEMENTED and VERIFIED.

Source of truth: `autopipe/core/run_state.py`. Every lifecycle write in the
system — executor, API, startup sweep — passes through `ensure_transition`.

## Run lifecycle

```
                 ┌──────────┐
                 │  PENDING │   created, queued behind a concurrency slot
                 └────┬─────┘
          ┌───────────┼─────────────┐
          ↓           ↓             ↓
     ┌────────┐  ┌─────────┐  ┌───────────┐
     │RUNNING │  │  FAILED │  │ CANCELLED │
     └───┬────┘  └─────────┘  └───────────┘
   ┌─────┼──────────┐
   ↓     ↓          ↓
SUCCESS FAILED CANCELLED
```

| From | To | Meaning |
|---|---|---|
| `PENDING` | `RUNNING` | a worker slot freed and execution started |
| `PENDING` | `FAILED` | the configuration could not be loaded/planned |
| `PENDING` | `CANCELLED` | cancelled while still queued |
| `RUNNING` | `SUCCESS` | every step completed |
| `RUNNING` | `FAILED` | a step failed, or the plan was invalid |
| `RUNNING` | `CANCELLED` | cancellation observed at a step boundary |
| terminal  | *(nothing)* | empty transition set |

## Step lifecycle

```
PENDING ──→ RUNNING ──→ SUCCESS
   │           │
   │           └──→ FAILED
   ├──→ FAILED            (finalized without a "started" write: crash recovery)
   └──→ SKIPPED           (upstream failure, cancellation)
RUNNING ──→ SKIPPED        (interrupted; must always be finalizable)
```

There is deliberately **no** `CANCELLED` step state: cancellation is a *run*
concept, and steps that never ran are `SKIPPED`. Asserted by
`test_step_states_have_no_cancelled_member`.

## Rules

1. **Single gate.** All writes go through `ensure_transition` (invariant I5).
   An unknown state raises; an illegal move raises `StateTransitionError`.
2. **Idempotent re-assertion is legal.** Re-writing the same state is allowed —
   the dashboard re-broadcasts RUNNING while writers race, and a recovery sweep
   may re-write an already-correct state.
3. **Terminal states are immutable** except through `allow_recovery=True`,
   which is greppable at every call site (invariant I6). Currently **no**
   production call site uses it: the startup sweep's `RUNNING → FAILED` is an
   ordinary legal transition.
4. **Wire compatibility.** `RunState`/`StepState` string values are identical to
   the pre-existing `RunStatus`/`StepStatus` database values, so adoption
   required **no schema or data migration**.
   (`test_run_state_values_match_persisted_wire_format`.)
5. **Corruption is not absence.** A recorded value that cannot be interpreted
   raises rather than being treated as "no prior state"
   (`test_unknown_current_state_is_rejected`).

## Enforcement and tests

| Rule | Test |
|---|---|
| legal transitions | `TestLegalTransitions` (parametrized) |
| illegal transitions raise | `TestTerminalImmutability`, `TestIdempotence` |
| terminal immutability | `test_no_legal_transition_leaves_a_terminal_state` |
| recovery override is explicit | `test_recovery_override_is_explicit_and_permitted` |
| coercion of wire values/names | `TestCoercion` |
| vocabularies are not interchangeable | `test_run_only_states_are_not_valid_step_states` |
| API rejects resurrection | `backend/tests/test_runs.py::test_cannot_resurrect_a_terminal_run` |

## Where each state is written

| Writer | Path | States it may set |
|---|---|---|
| Executor (worker thread) | `RunStateStore.mark_run_running` | `RUNNING` |
| Executor (worker thread) | `RunStateStore.finish_run` | `SUCCESS`/`FAILED`/`CANCELLED` |
| Executor (containment floor) | `runner._force_terminal` | `FAILED` |
| Startup sweep | `RunStateStore.sweep_orphaned` | `FAILED` (from `RUNNING`) |
| API | `PATCH /runs/{id}` via `ensure_transition` | any legal transition; 409 otherwise |
