# Execution Model

**Status:** IMPLEMENTED and VERIFIED (see `ARCHITECTURAL_INVARIANTS.md` for the
invariants and their tests).

## One execution semantic

There is exactly one implementation of what it means to execute a pipeline:

```
autopipe/core/execution.py
├── ExecutionEngine        the semantic: plan → bind → invoke → propagate
├── ExecutionContext       injected dependencies (no globals)
├── ExecutionResult        terminal outcome, always produced
├── StepOutcome            per-step record
├── ExecutionEvent/EventKind  the observation stream
├── EventSink (+ impls)    where observations go
└── CancellationToken      cooperative cancellation

autopipe/core/run_state.py
├── RunState / StepState   the lifecycle vocabulary
├── *_TRANSITIONS          the legal moves
└── ensure_transition      the single mutation gate
```

## Who calls the engine

| Caller | How | What it does with the result |
|---|---|---|
| Library API `Pipeline.run(initial_inputs)` | builds an `ExecutionContext` with a `NullEventSink` | re-raises `result.exception` (historical contract), returns `result.outputs` |
| CLI `autopipe run` | via `Pipeline.run` | prints the outputs table |
| Dashboard `POST /pipelines/{id}/runs` | `execute_run` → thread → `ExecutionEngine().execute` | persists events, broadcasts, guarantees a terminal write |
| Future worker | same engine, different sink | unchanged semantics |

The dashboard does **not** re-implement binding, ordering, lifecycle or
cancellation. `app/executor/runner.py` is a coordinator; the duplicate loop it
used to contain was deleted.

## Input binding (the semantic that used to diverge)

`resolve_step_inputs` precedence:

1. **Named bindings** — `step.input_bindings = {param: upstream}`; each `run()`
   parameter receives exactly the output of the step it names.
2. **`depends_on`** — otherwise `{upstream_name: output}` for every dependency
   that produced an output.
3. **`initial_inputs`** — otherwise the pipeline's initial inputs, verbatim.

Before this module existed, the dashboard loop implemented only rules 2 and 3, so
a YAML `inputs:` block was silently ignored there. Verified by
`test_named_bindings_are_honored_through_the_real_wiring`.

## Observation, not interception

The engine publishes `ExecutionEvent`s; it never calls the database. Consequences:

* the engine has **no** persistence dependency and can be unit-tested directly;
* a broken observer cannot decide execution — it is recorded in
  `result.sink_errors` and logged at WARNING (never silently dropped);
* adding a telemetry backend means adding a sink, not editing the engine.

## Failure containment

```
step raises  ─┐
cancellation ─┤
engine bug   ─┤
DB write fails┘
      ↓  ExecutionEngine.execute (never raises)
   ExecutionResult(state ∈ {SUCCESS, FAILED, CANCELLED})
      ↓  runner._finalize  (in a finally)
   RunStateStore.finish_run  →  terminal row + broadcast
      ↓  if that write itself fails
   runner._force_terminal  →  FAILED, or a CRITICAL log if even that fails
      ↓  always
   slot released · log handler detached · run unregistered
```

The guaranteed-cancellation granularity is the **step boundary**. A step may
cooperatively abort earlier via `step.cancellation_token` (injected by the
engine); that is an optimization, not the contract.

## Deliberate semantic decision: failure outranks cancellation

If a step fails and cancellation is requested afterwards, the run is **FAILED**,
not `CANCELLED`. A run that broke must not be able to report itself as merely
stopped — that would mask a real defect. Covered by
`test_failure_outranks_cancellation`.

## Known remaining limitations (not fabricated as solved)

- **Provenance** is partial (Tier 4): each run stores a sha256 of the config
  it executed (`Run.config_hash`); `engine_version` is available on the result
  but not yet persisted, and environment/data/seed provenance does not exist.
- **Multi-process deployment**: the run registry, WebSocket connection manager
  and rate limiter are per-process. Single-process is the supported topology.
- **`sys.path` bootstrap**: the backend venv does not install the core library,
  so `app/executor/__init__.py` inserts the repo root. Documented technical debt.
