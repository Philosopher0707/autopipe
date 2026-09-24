"""Background execution coordinator for dashboard-triggered pipeline runs.

This module is deliberately thin. It does **not** implement pipeline semantics:
it loads a configuration, hands the pipeline to the canonical engine
(:mod:`autopipe.core.execution`), projects the resulting events into the database
via :class:`app.executor.sink.RunEventSink`, and guarantees that every run
reaches a terminal state.

The execution loop that used to live here has been deleted. It had drifted from
the core loop — it ignored named input bindings (``inputs:`` in YAML) and never
assigned ``step.output`` — so the same pipeline behaved differently depending on
whether it was launched from the CLI or the dashboard. See
``docs/architecture/EXECUTION_MODEL.md``.

Failure containment (invariant I11)
-----------------------------------
``_run_pipeline_in_thread`` is the target of a daemon thread. Nothing may escape
it: an escaping exception used to kill the thread and leave the run row claiming
RUNNING forever, with no error message and no event, until the next process
restart swept it. This module therefore guarantees that:

* the engine never propagates (it returns a terminal ``ExecutionResult``),
* ``finally`` always attempts a terminal write,
* if that write itself fails, the failure is logged at CRITICAL level,
* the run slot, log handler and cancellation registration are always released.
"""

import asyncio
import contextvars
import logging
import threading
import time
import traceback
from typing import Any, Dict, Optional, Sequence

from app.core.config import settings
from app.executor.registry import register_run, unregister_run
from app.executor.sink import (
    RunEventSink,
    RunStateStore,
    _current_run_id,
    _WebSocketLogHandler,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from autopipe.core.artifacts import (
    drain_dataset_inputs,
    drain_model_identities,
    drain_produced_files,
)
from autopipe.core.execution import (
    ENGINE_VERSION,
    CancellationToken,
    EventKind,
    ExecutionContext,
    ExecutionEngine,
    ExecutionEvent,
    ExecutionResult,
)
from autopipe.core.run_state import RunState
from autopipe.exceptions import StateTransitionError

try:
    import psutil
except ImportError:  # pragma: no cover - optional runtime dependency
    psutil = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# Sync DB engine for background threads (SQLAlchemy async sessions cannot be used
# from a non-async thread). ``autopipe`` importability is established once in this
# package's ``__init__``, which runs before this module is imported.
_sync_engine: Any = None
_SyncSessionLocal: Optional[sessionmaker] = None
_sync_engine_lock = threading.Lock()

# Reference to the running event loop for scheduling async broadcasts. Retained
# as module state because existing callers (and tests) patch it; its value is
# passed explicitly into each RunEventSink rather than read by the sink itself.
_event_loop: Optional[asyncio.AbstractEventLoop] = None

# Upper bound on simultaneously executing pipeline runs. Each run occupies a
# daemon thread; unbounded spawning let N parallel requests exhaust memory.
MAX_CONCURRENT_RUNS = 4
_run_slots = threading.BoundedSemaphore(MAX_CONCURRENT_RUNS)

# Live executor threads by run id, so shutdown can cancel and join them
# instead of letting daemon threads die mid-write.
_live_threads: Dict[str, threading.Thread] = {}
_live_threads_lock = threading.Lock()


def _remember_thread(run_id: str, thread: threading.Thread) -> None:
    with _live_threads_lock:
        _live_threads[run_id] = thread


def _forget_thread(run_id: str) -> None:
    with _live_threads_lock:
        _live_threads.pop(run_id, None)


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Record the application event loop for thread -> loop broadcasts."""
    global _event_loop
    _event_loop = loop


def _configure_sqlite(engine: Any) -> None:
    """Apply the same SQLite hardening the async app engine uses.

    The executor previously created its own engine with none of these pragmas, so
    the code path that actually writes run/step rows ran with foreign keys OFF, a
    default busy timeout, and no WAL — while the API's engine had all three. That
    asymmetry is a data-integrity bug, not a tuning difference.
    """
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


def _get_sync_session_factory() -> sessionmaker:
    """Get or create the sync session factory for background threads."""
    global _sync_engine, _SyncSessionLocal
    if _SyncSessionLocal is not None:
        return _SyncSessionLocal

    with _sync_engine_lock:
        # Double-checked locking
        if _SyncSessionLocal is not None:
            return _SyncSessionLocal

        db_url = settings.DATABASE_URL
        db_url = db_url.replace("sqlite+aiosqlite://", "sqlite:///")
        if not db_url.startswith("sqlite"):
            db_url = db_url.replace("sqlite://", "sqlite:///")
        _sync_engine = create_engine(db_url, echo=False)
        if db_url.startswith("sqlite"):
            _configure_sqlite(_sync_engine)
        _SyncSessionLocal = sessionmaker(_sync_engine, expire_on_commit=False)
        return _SyncSessionLocal


def _load_pipeline(config: dict) -> Any:
    """Load a Pipeline from a config dict using the core loader."""
    from autopipe.core.loader import load_pipeline_from_config

    return load_pipeline_from_config(config)


def _collect_system_metrics() -> Dict[str, Any]:
    """Collect CPU and memory usage via psutil (best-effort telemetry)."""
    metrics: Dict[str, Any] = {}
    if not psutil:
        return metrics
    try:
        metrics["cpu_percent"] = round(psutil.cpu_percent(interval=0.1), 1)
        metrics["memory_percent"] = round(psutil.virtual_memory().percent, 1)
    except Exception:
        logger.debug("psutil CPU/memory metrics failed", exc_info=True)
    return metrics


def _load_failure_result(
    run_id: str,
    pipeline_name: str,
    exc: Exception,
    sink: RunEventSink,
    cancelled: bool,
) -> ExecutionResult:
    """Build a FAILED result for a configuration that never became a pipeline.

    A configuration that cannot be loaded never reaches the engine, so the engine
    cannot produce its ``RUN_STARTED`` event. Emitting it here keeps the event
    stream shape identical to every other failure (a plan that could not be
    resolved), so consumers need no special case.
    """
    message = f"Pipeline load error: {exc}"
    now = time.time()
    state = RunState.CANCELLED if cancelled else RunState.FAILED
    sink.emit(
        ExecutionEvent(
            kind=EventKind.RUN_STARTED,
            run_id=run_id,
            sequence=0,
            timestamp=now,
            state=RunState.RUNNING.value,
            data={"execution_order": [], "plan_resolved": False},
            error=message,
            error_type=type(exc).__name__,
        )
    )
    return ExecutionResult(
        run_id=run_id,
        pipeline_name=pipeline_name,
        state=state,
        started_at=now,
        finished_at=now,
        error=message,
        error_type=type(exc).__name__,
        exception=exc,
        engine_version=ENGINE_VERSION,
    )


def _execute(
    run_id: str,
    pipeline_config: dict,
    initial_inputs: Optional[dict],
    cancel_event: threading.Event,
    sink: RunEventSink,
) -> ExecutionResult:
    """Load the pipeline and run it on the canonical engine.

    Loading is not execution: a configuration that cannot be instantiated is
    reported as a FAILED result rather than handed to the engine, because there
    is no pipeline object for the engine to plan.
    """
    pipeline_name = str((pipeline_config or {}).get("name") or run_id)
    try:
        pipeline = _load_pipeline(pipeline_config)
    except Exception as exc:
        logger.error("Failed to load pipeline for run %s: %s", run_id, exc)
        return _load_failure_result(run_id, pipeline_name, exc, sink, cancel_event.is_set())

    raw_seed = (pipeline_config or {}).get("seed")
    seed = raw_seed if type(raw_seed) is int and raw_seed >= 0 else None
    context = ExecutionContext(
        run_id=run_id,
        pipeline_name=str(getattr(pipeline, "name", pipeline_name)),
        initial_inputs=dict(initial_inputs) if initial_inputs else None,
        seed=seed,
        # The registry's event *is* the token's event, so a PATCH /runs/{id}
        # cancellation reaches the engine without polling a second flag.
        cancellation=CancellationToken(cancel_event),
        sink=sink,
        metadata={"origin": "dashboard", "engine": ENGINE_VERSION},
    )
    return ExecutionEngine().execute(pipeline, context)


def _finalize(
    run_id: str,
    result: ExecutionResult | None,
    store: RunStateStore,
    produced: Optional[Sequence[str]] = None,
    datasets: Optional[Sequence[dict]] = None,
    models: Optional[Sequence[dict]] = None,
) -> None:
    """Write the terminal state. The single place a dashboard run's life ends.

    A ``None`` result means the engine never produced one (an escape inside
    ``_execute``), in which case the run is forced into FAILED. Any persistence
    failure here is logged loudly rather than left to rot the row.
    ``produced`` is the drained list of files the run wrote (Phase B artifact
    registration), ``datasets`` the drained dataset-input entries (Phase C
    input identity) and ``models`` the drained response-supplied model
    identities (Track A resolved model identity); all are persisted only when
    a valid result exists.
    """
    if result is None:
        _force_terminal(run_id, store)
        return

    # Evidence bridges first, terminal write second: a persistence failure here
    # must never prevent the run from reaching its final state.
    if result.seed_applied is not None:
        try:
            store.record_seed_applied(run_id, result.seed_applied)
        except Exception:
            logger.exception("Failed to record seed application for run %s", run_id)
    if produced:
        try:
            store.register_artifacts(run_id, produced)
        except Exception:
            logger.exception("Failed to register artifacts for run %s", run_id)
    if datasets:
        try:
            store.record_dataset_inputs(run_id, datasets)
        except Exception:
            logger.exception("Failed to record dataset inputs for run %s", run_id)
    if models:
        try:
            store.record_model_identity(run_id, models)
        except Exception:
            logger.exception("Failed to record model identity for run %s", run_id)
    try:
        store.record_drift(run_id, result.outputs)
    except Exception:
        logger.exception("Failed to persist drift reports for run %s", run_id)

    metrics = dict(result.metrics)
    if result.state is RunState.SUCCESS:
        metrics.update(_collect_system_metrics())

    persisted = store.finish_run(
        run_id,
        result.state,
        error=result.error,
        metrics=metrics or None,
        loop=_event_loop,
    )
    if not persisted:
        logger.critical(
            "Run %s terminal state %s was NOT persisted to the database",
            run_id,
            result.state.value,
        )
    if result.sink_errors:
        logger.warning(
            "Run %s recorded %d observability failure(s): %s",
            run_id,
            len(result.sink_errors),
            result.sink_errors[:3],
        )
    logger.info(
        "Run %s finished as %s in %.3fs", run_id, result.state.value, result.duration_seconds
    )


def _force_terminal(run_id: str, store: RunStateStore) -> None:
    """Last-resort terminal write when the engine never returned a result.

    No recovery override is used: ``PENDING -> FAILED`` and ``RUNNING -> FAILED``
    are ordinary legal transitions. If the run already reached a terminal state
    there is nothing to force. If the write itself fails, all that remains is to
    say so at the highest severity.
    """
    try:
        store.finish_run(
            run_id,
            RunState.FAILED,
            error="Execution aborted by an internal error",
            loop=_event_loop,
        )
    except StateTransitionError:
        logger.info("Run %s is already terminal; nothing to force", run_id)
    except BaseException:
        logger.critical("Could not force run %s into a terminal state", run_id, exc_info=True)


def _run_pipeline_in_thread(
    run_id: str, pipeline_config: dict, initial_inputs: Optional[dict] = None
) -> None:
    """Execute one run on the canonical engine. Guaranteed not to raise.

    This is a daemon-thread target: an escaping exception would kill the thread
    and leave the run row claiming RUNNING forever. **Every** operation —
    store creation, registration, slot acquisition, execution — lives inside
    the containment boundary below; the previous version performed prologue
    work outside the try, violating its own rule. When a store exists, a
    terminal write is always attempted; when it does not, the failure is
    logged at CRITICAL and the startup sweep recovers the row.
    """
    store: Optional[RunStateStore] = None
    sink: Optional[RunEventSink] = None
    token: Optional[contextvars.Token] = None
    registered = False
    slot_acquired = False
    result: Optional[ExecutionResult] = None
    produced: Sequence[str] = ()
    datasets: Sequence[dict] = ()
    models: Sequence[dict] = ()

    try:
        drain_produced_files()  # clear any leftovers from a prior in-thread test run
        drain_dataset_inputs()
        drain_model_identities()
        SessionLocal = _get_sync_session_factory()
        store = RunStateStore(SessionLocal)
        cancel_event = register_run(run_id)
        registered = True
        token = _current_run_id.set(run_id)
        sink = RunEventSink(run_id, store, loop=_event_loop)
        _run_slots.acquire()
        slot_acquired = True
        result = _execute(run_id, pipeline_config, initial_inputs, cancel_event, sink)
    except BaseException as exc:
        logger.critical(
            "Run %s escaped setup or execution: %s: %s\n%s",
            run_id,
            type(exc).__name__,
            exc,
            traceback.format_exc(),
        )
    finally:
        produced = drain_produced_files()
        datasets = drain_dataset_inputs()
        models = drain_model_identities()
        # close and finalize are independent: a failing close must not skip
        # the terminal write (it used to share one try, so a close error
        # routed through _force_terminal and could overwrite a valid result).
        if sink is not None:
            try:
                sink.close()
            except BaseException:
                logger.critical("Run %s sink close failed", run_id, exc_info=True)
        if store is not None:
            try:
                _finalize(
                    run_id, result, store, produced=produced, datasets=datasets, models=models
                )
            except BaseException:
                logger.critical("Run %s could not be finalized", run_id, exc_info=True)
                _force_terminal(run_id, store)
        else:
            logger.critical(
                "Run %s has no state store; terminal write impossible until startup sweep",
                run_id,
            )
        if slot_acquired:
            _run_slots.release()
        if token is not None:
            _current_run_id.reset(token)
        if registered:
            unregister_run(run_id)
        _forget_thread(run_id)


async def execute_run(
    run_id: str, pipeline_config: dict, initial_inputs: Optional[dict] = None
) -> None:
    """Launch a pipeline run in a background thread.

    The async entry point called by FastAPI BackgroundTasks. It captures the
    current event loop for WebSocket broadcasts, then spawns a daemon thread for
    the actual work.
    """
    global _event_loop
    try:
        _event_loop = asyncio.get_running_loop()
    except RuntimeError:
        _event_loop = None

    thread = threading.Thread(
        target=_run_pipeline_in_thread,
        args=(str(run_id), pipeline_config, initial_inputs),
        daemon=True,
        name=f"pipeline-run-{str(run_id)[:8]}",
    )
    _remember_thread(str(run_id), thread)
    thread.start()


def shutdown_executor(timeout: float = 5.0) -> None:
    """Cancel active runs, join their threads, then sweep anything left.

    Daemon threads die with the process; without this, a graceful shutdown
    left rows claiming RUNNING until the *next* boot's sweep, and in-memory
    error context was lost. Called from the FastAPI stop handler before the
    database is closed.
    """
    from app.executor.registry import get_active_run_ids

    for run_id in get_active_run_ids():
        cancel_run(run_id)

    with _live_threads_lock:
        threads = list(_live_threads.values())
    deadline = time.monotonic() + timeout
    for t in threads:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        t.join(timeout=remaining)

    try:
        swept = sweep_orphaned_runs()
        if swept:
            logger.warning("Shutdown sweep marked %d non-terminal run(s) FAILED", swept)
    except BaseException:
        logger.critical("Shutdown sweep failed", exc_info=True)


def sweep_orphaned_runs() -> int:
    """Mark runs/steps left RUNNING by a dead process as FAILED.

    A crash or restart leaves rows claiming active execution forever; the UI then
    shows phantom running pipelines. Called once at application startup, before
    any new run can be dispatched. This is the sanctioned recovery path — the
    ``RUNNING -> FAILED`` transition is ordinary and legal.
    """
    SessionLocal = _get_sync_session_factory()
    return RunStateStore(SessionLocal).sweep_orphaned()


# --------------------------------------------------------------------------
# Re-exports
#
# These names have callers in endpoints and tests outside this module. They are
# gathered here deliberately so that the set of symbols other code may rely on
# is explicit rather than "whatever happens to be module-level".
# --------------------------------------------------------------------------
from app.executor.registry import cancel_run  # noqa: E402  (re-export)
from app.executor.sink import schedule_broadcast  # noqa: E402  (re-export)

__all__ = [
    "MAX_CONCURRENT_RUNS",
    "_WebSocketLogHandler",
    "_current_run_id",
    "_event_loop",
    "_get_sync_session_factory",
    "_run_pipeline_in_thread",
    "cancel_run",
    "execute_run",
    "schedule_broadcast",
    "set_event_loop",
    "shutdown_executor",
    "sweep_orphaned_runs",
]
