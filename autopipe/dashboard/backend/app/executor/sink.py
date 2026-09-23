"""Projection of engine execution events into dashboard state.

This module owns **persistence and telemetry** — never execution. The canonical
engine publishes :class:`~autopipe.core.execution.ExecutionEvent`s; this module
is the only place in the dashboard that turns them into ``Run``/``Step`` rows and
WebSocket messages.

Architecture::

    ExecutionEngine  --events-->  RunEventSink  --writes-->  RunStateStore
                                  (this module)               (this module)

``RunStateStore`` is the **single owner** of persisted run/step lifecycle state
(invariant I5). Every write passes through
:func:`autopipe.core.run_state.ensure_transition`, so an illegal transition is
rejected rather than silently applied (invariant I6).
"""

import asyncio
import contextvars
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

from app.db.models import (
    AlertSeverity,
    Artifact,
    DriftAlert,
    DriftReport,
    MetricLog,
    Run,
    RunStatus,
    Step,
    StepStatus,
)
from app.utils.datetime_utils import safe_duration_seconds
from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

from autopipe.core.execution import EventKind, ExecutionEvent
from autopipe.core.run_state import RunState, StepState, ensure_transition
from autopipe.exceptions import StateTransitionError

logger = logging.getLogger(__name__)

# Identifies which run a background thread is executing. Log handlers use it to
# keep concurrent runs' records out of each other's WebSocket streams. This is a
# ContextVar rather than a global because it is genuinely per-thread state.
_current_run_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_run_id", default=None
)


def schedule_broadcast(build: Callable[[], Any], loop: Optional[asyncio.AbstractEventLoop]) -> None:
    """Schedule a broadcast coroutine on the loop from a non-async thread.

    ``build`` is a zero-argument callable that *returns* the coroutine; it is only
    invoked when a loop is available, so no un-awaited coroutine is ever created
    on the "no loop" path (which would leak and warn). The loop is an explicit
    dependency: this module holds no process-wide loop reference.

    Failure is never fatal — telemetry must not decide execution — but it is
    logged at warning level rather than silently dropped.
    """
    if loop is None:
        logger.debug("No event loop supplied; skipping broadcast")
        return
    try:
        asyncio.run_coroutine_threadsafe(build(), loop)
    except RuntimeError:
        logger.warning("Failed to schedule broadcast on the event loop", exc_info=True)


def _broadcast_run_status(
    run_id: str,
    status: str,
    data: Optional[dict] = None,
    loop: Optional[asyncio.AbstractEventLoop] = None,
) -> None:
    """Broadcast a run status change."""
    from app.api.v1.endpoints.websocket import broadcast_run_status

    schedule_broadcast(lambda: broadcast_run_status(run_id, status, data), loop)


def _broadcast_step_log(
    run_id: str,
    step_id: str,
    level: str,
    message: str,
    loop: Optional[asyncio.AbstractEventLoop] = None,
) -> None:
    """Broadcast a log line against a step."""
    from app.api.v1.endpoints.websocket import broadcast_run_log

    schedule_broadcast(lambda: broadcast_run_log(run_id, step_id, level, message), loop)


def _broadcast_step_metric(
    run_id: str,
    step_id: str,
    metric_name: str,
    value: float,
    loop: Optional[asyncio.AbstractEventLoop] = None,
) -> None:
    """Broadcast a single step metric."""
    from app.api.v1.endpoints.websocket import broadcast_run_metric

    schedule_broadcast(lambda: broadcast_run_metric(run_id, step_id, metric_name, value), loop)


class _WebSocketLogHandler(logging.Handler):
    """Captures ``autopipe`` log records during a step and streams them.

    Records emitted by *other* concurrently-running pipelines are dropped: the
    ``autopipe`` logger tree is shared across threads, so without this guard run
    B's step logs would stream into run A's channel.
    """

    def __init__(
        self,
        run_id: str,
        step_id: str,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        super().__init__()
        self.run_id = run_id
        self.step_id = step_id
        self._loop = loop

    def filter(self, record: logging.LogRecord) -> bool:
        """Keep only records emitted while *this* run is the active run."""
        return _current_run_id.get() == self.run_id

    def emit(self, record: logging.LogRecord) -> None:
        """Format and forward the record; never raise into the logging system."""
        try:
            message = self.format(record)
            _broadcast_step_log(
                self.run_id,
                self.step_id,
                record.levelname,
                message,
                self._loop,
            )
        except Exception:
            logger.debug("WebSocket log broadcast failed", exc_info=True)


class _StepLogCapture:
    """Attaches a :class:`_WebSocketLogHandler` for the duration of one step."""

    def __init__(
        self,
        run_id: str,
        step_id: str,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        self.handler = _WebSocketLogHandler(run_id, step_id, loop)
        self.handler.setLevel(logging.DEBUG)
        self.logger = logging.getLogger("autopipe")

    def start(self) -> "_StepLogCapture":
        """Attach the handler and return self."""
        self.logger.addHandler(self.handler)
        return self

    def stop(self) -> None:
        """Detach the handler. Safe to call more than once."""
        self.logger.removeHandler(self.handler)


def _infer_artifact_type(path: str) -> str:
    """Best-effort ``artifact_type`` from the file extension."""
    ext = os.path.splitext(path)[1].lower()
    if ext in {".png", ".jpg", ".jpeg", ".svg", ".pdf", ".html"}:
        return "plot"
    if ext in {".pkl", ".joblib", ".pt", ".pth", ".keras", ".onnx", ".h5"}:
        return "model"
    return "data"


def _run_state_value(run: Run) -> Optional[str]:
    """Current run status as a wire string, or None when unset."""
    status = run.status
    if status is None:
        return None
    return status.value if hasattr(status, "value") else str(status)


def _step_state_value(step: Step) -> Optional[str]:
    """Current step status as a wire string, or None when unset."""
    status = step.status
    if status is None:
        return None
    return status.value if hasattr(status, "value") else str(status)


def _run_status_values(
    run: Run,
    state: RunState,
    *,
    error: Optional[str] = None,
    metrics: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Column values for a run status transition, including implied timestamps."""
    values: Dict[str, Any] = {"status": RunStatus(state.value)}
    now = datetime.now(timezone.utc)
    if state is RunState.RUNNING and run.started_at is None:
        values["started_at"] = now
    if state.is_terminal:
        values["completed_at"] = now
        if run.started_at is not None:
            values["duration_seconds"] = safe_duration_seconds(run.started_at, now)
    if error:
        values["error_message"] = error
    if metrics:
        values["metrics"] = dict(metrics)
    return values


def _cas_run_status(
    db: Any,
    run_id: str,
    expected: Any,
    state: RunState,
    *,
    error: Optional[str] = None,
    metrics: Optional[Mapping[str, Any]] = None,
) -> bool:
    """Atomically transition a run only if its status is still ``expected``.

    Returns True when the row was updated. Returns False when the row is
    missing or another writer already moved it (caller decides whether that
    is idempotent success or a conflict).
    """
    run = db.get(Run, run_id)
    if run is None:
        return False
    values = _run_status_values(run, state, error=error, metrics=metrics)
    result = db.execute(
        update(Run).where(Run.id == run_id, Run.status == expected).values(**values)
    )
    return result.rowcount >= 1


def _cas_step_status(
    db: Any,
    step_id: str,
    expected: Any,
    state: StepState,
    *,
    error: Optional[str] = None,
    metrics: Optional[Mapping[str, Any]] = None,
) -> bool:
    """Atomically transition a step only if its status is still ``expected``."""
    step = db.get(Step, step_id)
    if step is None:
        return False
    values: Dict[str, Any] = {"status": StepStatus(state.value)}
    now = datetime.now(timezone.utc)
    if state is StepState.RUNNING and step.started_at is None:
        values["started_at"] = now
    if state.is_terminal:
        values["completed_at"] = now
        if step.started_at is not None:
            values["duration_seconds"] = safe_duration_seconds(step.started_at, now)
    if error:
        values["error_message"] = error
    if metrics:
        values["metrics"] = dict(metrics)
    result = db.execute(
        update(Step).where(Step.id == step_id, Step.status == expected).values(**values)
    )
    return result.rowcount >= 1


def _conflict_error(context: str, expected: object, actual: object) -> StateTransitionError:
    return StateTransitionError(
        f"Concurrent status change ({context}): expected {expected}, found {actual}",
        details={"expected": str(expected), "actual": str(actual), "context": context},
    )


def _insert_metric_logs(
    db: Any,
    run_id: str,
    step_id: str,
    step_index: Optional[int],
    metrics: Mapping[str, Any],
) -> int:
    """Append numeric step metrics to the MetricLog time series.

    Called inside the mark_step transaction, so a CAS rollback discards the
    rows with the status write — a conflict never leaves orphan points.
    Non-numeric values and bools are skipped (they are not scalar series).
    """
    run = db.get(Run, run_id)
    added = 0
    for name, value in metrics.items():
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            db.add(
                MetricLog(
                    run_id=run_id,
                    step_id=step_id,
                    pipeline_id=run.pipeline_id if run else None,
                    experiment_id=run.experiment_id if run else None,
                    metric_name=str(name)[:255],
                    step_index=step_index,
                    value=float(value),
                )
            )
            added += 1
    return added


def _core_report_to_dict(report: Any) -> Optional[Dict[str, Any]]:
    """Accept both ``DriftReport.to_dict()`` payloads and live dataclass instances."""
    if isinstance(report, dict):
        return report
    to_dict = getattr(report, "to_dict", None)
    if callable(to_dict):
        try:
            value = to_dict()
            return value if isinstance(value, dict) else None
        except Exception:
            return None
    return None


def _collect_drift_batches(node: Any, depth: int = 3) -> list:
    """Find every dict carrying ``drift_reports``, up to ``depth`` dict levels.

    ``StatisticalDriftDetectorStep`` returns the batch at the top of its step
    output; ``DriftDashboardStep`` nests it under ``feature_drift``. A found
    batch is not descended into (its values are report entries, not batches).
    """
    if not isinstance(node, dict) or depth < 0:
        return []
    if node.get("drift_reports"):
        return [node]
    found: list = []
    for value in node.values():
        found.extend(_collect_drift_batches(value, depth - 1))
    return found


class RunStateStore:
    """The single owner of persisted run/step lifecycle state (invariant I5).

    Before this class existed, three code paths wrote ``Run.status`` directly:
    the API's PATCH handler, the executor thread, and the startup sweep. They had
    no shared notion of which transitions were legal, so a terminal run could be
    silently resurrected.

    Every write here goes through
    :func:`autopipe.core.run_state.ensure_transition`; an illegal transition
    raises :class:`~autopipe.exceptions.StateTransitionError` instead of being
    applied.
    """

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def mark_run_running(self, run_id: str, loop: Any = None) -> bool:
        """Transition a run to RUNNING via compare-and-swap.

        Returns:
            True when the run was found and moved; False when the row is missing.
        """
        with self._session_factory() as db:
            run = db.get(Run, run_id)
            if run is None:
                logger.error("Run %s not found; cannot start execution", run_id)
                return False
            expected = run.status
            state = ensure_transition(
                _run_state_value(run), RunState.RUNNING, context=f"run={run_id}"
            )
            if not _cas_run_status(db, run_id, expected, state):
                db.rollback()
                fresh = db.get(Run, run_id)
                actual = fresh.status if fresh else None
                raise _conflict_error(f"run={run_id}", expected, actual)
            db.commit()
        _broadcast_run_status(run_id, RunState.RUNNING.value, None, loop)
        return True

    def finish_run(
        self,
        run_id: str,
        state: RunState,
        *,
        error: Optional[str] = None,
        metrics: Optional[Mapping[str, Any]] = None,
        loop: Any = None,
    ) -> bool:
        """Finalize a run into a terminal state via compare-and-swap.

        Returns:
            True when the terminal state was persisted (or the row is already
            in that same terminal state — an idempotent re-assert); False when
            the row is missing. A conflicting concurrent write raises
            :class:`StateTransitionError`.
        """
        with self._session_factory() as db:
            run = db.get(Run, run_id)
            if run is None:
                logger.error("Run %s not found; cannot finalize as %s", run_id, state.value)
                return False
            expected = run.status
            resolved = ensure_transition(_run_state_value(run), state, context=f"run={run_id}")
            if not _cas_run_status(db, run_id, expected, resolved, error=error, metrics=metrics):
                db.rollback()
                fresh = db.get(Run, run_id)
                if fresh is None:
                    return False
                actual = _run_state_value(fresh)
                # Another writer already landed the same terminal state.
                if actual == resolved.value:
                    return True
                raise _conflict_error(f"run={run_id}", expected, actual)
            db.commit()

        payload: Dict[str, Any] = {}
        if error:
            payload["error_message"] = error
        if metrics:
            payload["metrics"] = dict(metrics)
        _broadcast_run_status(run_id, state.value, payload or None, loop)
        return True

    def create_steps(
        self,
        run_id: str,
        execution_order: Sequence[str],
        step_types: Mapping[str, str],
    ) -> Dict[str, str]:
        """Pre-create the planned steps as PENDING so the UI can show the plan.

        Returns:
            Mapping of step name to the database id assigned to it.
        """
        step_ids: Dict[str, str] = {}
        with self._session_factory() as db:
            for index, name in enumerate(execution_order):
                row = Step(
                    run_id=run_id,
                    name=name,
                    step_type=step_types.get(name, "unknown"),
                    status=StepStatus.PENDING,
                    order_index=index,
                )
                db.add(row)
                db.flush()
                step_ids[name] = row.id
            db.commit()
        return step_ids

    def mark_step(
        self,
        run_id: str,
        step_name: str,
        state: StepState,
        *,
        metrics: Optional[Mapping[str, Any]] = None,
        error: Optional[str] = None,
        loop: Any = None,
    ) -> None:
        """Transition one step via compare-and-swap, and mirror metrics."""
        with self._session_factory() as db:
            row = db.scalars(
                select(Step).where(Step.run_id == run_id, Step.name == step_name)
            ).first()
            if row is None:
                logger.error(
                    "Step '%s' of run %s not found; cannot mark %s",
                    step_name,
                    run_id,
                    state.value,
                )
                return
            expected = row.status
            step_id = row.id
            resolved = ensure_transition(
                _step_state_value(row),
                state,
                subject="step",
                context=f"run={run_id} step={step_name}",
            )
            if not _cas_step_status(db, step_id, expected, resolved, error=error, metrics=metrics):
                db.rollback()
                fresh = db.get(Step, step_id)
                actual = fresh.status if fresh else None
                raise _conflict_error(f"run={run_id} step={step_name}", expected, actual)
            if metrics:
                _insert_metric_logs(db, run_id, step_id, row.order_index, metrics)
            db.commit()

        _broadcast_step_log(run_id, step_id, "info", f"Step {step_name}: {state.value}", loop)
        if metrics and state is StepState.SUCCESS:
            for metric_name, value in metrics.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    _broadcast_step_metric(run_id, step_id, metric_name, float(value), loop)

    def record_drift(self, run_id: str, outputs: Optional[Mapping[str, Any]]) -> int:
        """Bridge detector step outputs (core ``DriftReport``) into durable rows.

        One dashboard ``DriftReport`` row per step output that carries
        ``drift_reports``; per-feature details keep the core ``to_dict()``
        field names, which ``normalize_feature_drifts`` already understands
        (ROADMAP G3). ``DriftAlert`` rows are created for features the
        detector flagged. Returns the number of report rows written; a
        missing run or no detector outputs writes nothing. Invoked exactly
        once per run from ``runner._finalize`` (before the terminal write),
        so no dedup key is needed; a persistence failure propagates to the
        caller's containment.
        """
        batches = _collect_drift_batches(outputs or {})
        if not batches:
            return 0
        written = 0
        with self._session_factory() as db:
            if db.get(Run, run_id) is None:
                logger.error("Run %s not found; cannot record drift reports", run_id)
                return 0
            for payload in batches:
                feature_drifts: Dict[str, Dict[str, Any]] = {}
                drifted = 0
                for raw in payload["drift_reports"]:
                    details = _core_report_to_dict(raw)
                    if not details or not details.get("feature_name"):
                        continue
                    feature_drifts[str(details["feature_name"])] = details
                    if details.get("drift_detected"):
                        drifted += 1
                if not feature_drifts:
                    continue
                ratio = payload.get("drift_ratio")
                if not isinstance(ratio, (int, float)) or isinstance(ratio, bool):
                    ratio = drifted / len(feature_drifts)
                row = DriftReport(
                    run_id=run_id,
                    drift_score=float(ratio),
                    drift_detected=drifted > 0,
                    feature_drifts=feature_drifts,
                    alert_generated=drifted > 0,
                )
                db.add(row)
                db.flush()  # populate row.id (server-side default) for alert FKs
                for name, details in feature_drifts.items():
                    if not details.get("drift_detected"):
                        continue
                    db.add(
                        DriftAlert(
                            drift_report_id=row.id,
                            feature_name=name[:255],
                            severity=AlertSeverity.WARNING,
                            drift_type="feature",
                            drift_metric=str(details.get("metric_name") or "unknown")[:50],
                            drift_score=float(details.get("metric_value") or 0.0),
                            threshold=float(details.get("threshold") or 0.0),
                        )
                    )
                written += 1
            db.commit()
        return written

    def record_seed_applied(self, run_id: str, seed: int) -> None:
        """Record that the engine applied the declared seed to run-local RNG.

        Writes ``provenance["seed_applied"]`` — the runtime fact, distinct from
        the config's *declared* seed that ``build_provenance`` puts in
        ``provenance["seeds"]`` at Run creation. Called once per seeded run
        from ``runner._finalize`` before the terminal write (contained like
        ``record_drift``); a missing run logs and writes nothing.
        """
        with self._session_factory() as db:
            run = db.get(Run, run_id)
            if run is None:
                logger.error("Run %s not found; cannot record seed application", run_id)
                return
            prov = dict(run.provenance or {})
            prov["seed_applied"] = seed
            run.provenance = prov  # reassignment (not in-place mutation) marks dirty
            db.commit()

    def record_dataset_inputs(self, run_id: str, entries: Sequence[Mapping[str, Any]]) -> None:
        """Persist ``provenance["datasets"]`` — the inputs this run consumed.

        Entries are built by the loaders themselves (file: source + read-time
        sha256; builtin: name + "unavailable"; sql: format only — connection
        strings are never recorded, I12). Non-dict entries are skipped.
        Sibling provenance keys (seed_applied, origin, ...) survive the merge.
        Called once from ``runner._finalize`` before the terminal write,
        contained like ``record_drift``; a missing run logs and writes nothing.
        """
        clean = [dict(e) for e in entries if isinstance(e, Mapping)]
        if not clean:
            return
        with self._session_factory() as db:
            run = db.get(Run, run_id)
            if run is None:
                logger.error("Run %s not found; cannot record dataset inputs", run_id)
                return
            prov = dict(run.provenance or {})
            prov["datasets"] = clean
            run.provenance = prov  # reassignment (not in-place mutation) marks dirty
            db.commit()

    def register_artifacts(self, run_id: str, paths: Sequence[str]) -> int:
        """Insert Artifact rows for files produced during a run (one canonical writer).

        Uses the ``Artifact.file_path`` validator hook to compute ``sha256``
        (fail-closed: an OSError skips that file and continues). Idempotent
        per ``(run_id, file_path)``: a path already registered for this run
        is skipped. ``step_id`` is left NULL (no step association in Phase B).
        Returns the number of rows written; a missing run logs and writes
        nothing. Invoked once from ``runner._finalize`` before the terminal
        write, contained like ``record_drift``.
        """
        if not paths:
            return 0
        written = 0
        with self._session_factory() as db:
            if db.get(Run, run_id) is None:
                logger.error("Run %s not found; cannot register artifacts", run_id)
                return 0
            existing = {
                p
                for (p,) in db.execute(select(Artifact.file_path).where(Artifact.run_id == run_id))
            }
            seen: set = set(existing)
            for raw in paths:
                path = os.path.abspath(str(raw))
                if path in seen:
                    continue
                if not os.path.isfile(path):
                    logger.warning("Skipping produced file %s: not a file", raw)
                    continue
                try:
                    row = Artifact(
                        run_id=run_id,
                        name=os.path.basename(path)[:255],
                        artifact_type=_infer_artifact_type(path),
                        file_path=path,
                        file_size=os.path.getsize(path),
                    )
                    db.add(row)
                    seen.add(path)
                    written += 1
                except OSError as exc:
                    # sha256_file is fail-closed: skip this file, keep the rest
                    logger.warning("Skipping produced file %s: %s", raw, exc)
            db.commit()
        return written

    def sweep_orphaned(self) -> int:
        """Mark runs left RUNNING or PENDING by a dead process as FAILED.

        A crash or restart leaves rows claiming active execution forever; the UI
        then shows phantom running pipelines. PENDING is included because
        ``BackgroundTasks`` do not survive a restart: a run committed but never
        dispatched would otherwise stay PENDING forever (violating I12).
        Called once at application startup, before any new run can be dispatched.

        Goes through ``ensure_transition`` like every other writer, then CASes
        the write so a row that changed between SELECT and UPDATE is left alone.
        """
        swept = 0
        with self._session_factory() as db:
            for run in db.scalars(
                select(Run).where(Run.status.in_([RunStatus.RUNNING, RunStatus.PENDING]))
            ).all():
                was = run.status
                state = ensure_transition(
                    _run_state_value(run), RunState.FAILED, context=f"sweep run={run.id}"
                )
                if not _cas_run_status(
                    db, run.id, was, state, error="Interrupted by server restart"
                ):
                    logger.debug("Sweep skipped run %s (concurrent write)", run.id)
                    continue
                swept += 1
                logger.debug("Swept %s run %s at startup", was, run.id)
            for step in db.scalars(select(Step).where(Step.status == StepStatus.RUNNING)).all():
                was_step = step.status
                state = ensure_transition(
                    _step_state_value(step),
                    StepState.FAILED,
                    subject="step",
                    context=f"sweep step={step.id}",
                )
                if not _cas_step_status(
                    db, step.id, was_step, state, error="Interrupted by server restart"
                ):
                    continue
            db.commit()
        if swept:
            logger.warning("Swept %d orphaned PENDING/RUNNING run(s) at startup", swept)
        return swept


class RunEventSink:
    """Projects one run's engine events into rows and WebSocket messages.

    Implements the engine's :class:`~autopipe.core.execution.EventSink` protocol.
    One instance per run, called only from that run's worker thread, so it holds
    per-step state without locking.

    ``RUN_FINISHED`` is deliberately **not** handled here: the terminal write is
    owned by the runner's guaranteed-finalization path, which must execute even
    when this sink has already failed. Keeping exactly one writer for the
    terminal transition avoids two paths racing over the end of a run's life.
    """

    def __init__(
        self,
        run_id: str,
        store: RunStateStore,
        *,
        loop: Any = None,
        capture_logs: bool = True,
    ) -> None:
        self.run_id = run_id
        self._store = store
        self._loop = loop
        self._capture_logs = capture_logs
        self._step_ids: Dict[str, str] = {}
        self._capture: Optional[_StepLogCapture] = None

    # -- EventSink protocol -------------------------------------------------

    def emit(self, event: ExecutionEvent) -> None:
        """Translate one engine event into dashboard state."""
        if event.kind is EventKind.RUN_STARTED:
            self._on_run_started(event)
        elif event.kind is EventKind.STEP_STARTED:
            self._on_step_started(event)
        elif event.kind is EventKind.STEP_FINISHED:
            self._on_step_finished(event)
        elif event.kind is EventKind.STEP_SKIPPED:
            self._on_step_skipped(event)
        elif event.kind is EventKind.VISUALIZATION_FAILED:
            self._on_visualization_failed(event)

    # -- handlers -----------------------------------------------------------

    def _on_run_started(self, event: ExecutionEvent) -> None:
        """Mark the run RUNNING and materialize its planned steps."""
        try:
            self._store.mark_run_running(self.run_id, self._loop)
        except StateTransitionError:
            # The API finalized this run (e.g. CANCELLED) before the executor
            # reached RUN_STARTED. The terminal row must stay put, but planned
            # steps are still created so they can be written off as SKIPPED.
            logger.info(
                "Run %s already terminal at RUN_STARTED; materializing steps only",
                self.run_id,
            )
        order = list(event.data.get("execution_order") or [])
        step_types = dict(event.data.get("step_types") or {})
        if event.data.get("plan_resolved") and order:
            self._step_ids = self._store.create_steps(self.run_id, order, step_types)

    def _on_step_started(self, event: ExecutionEvent) -> None:
        """Mark the step RUNNING and begin streaming its logs."""
        name = event.step_name or ""
        self._store.mark_step(self.run_id, name, StepState.RUNNING, loop=self._loop)
        self._stop_capture()
        step_id = self._step_ids.get(name)
        if step_id and self._capture_logs:
            self._capture = _StepLogCapture(self.run_id, step_id, self._loop).start()

    def _on_step_finished(self, event: ExecutionEvent) -> None:
        """Persist the step's terminal state, metrics and error."""
        name = event.step_name or ""
        self._stop_capture()
        state = StepState(event.state) if event.state else StepState.FAILED
        metrics = event.data.get("metrics") or None
        self._store.mark_step(
            self.run_id,
            name,
            state,
            metrics=metrics,
            error=event.error,
            loop=self._loop,
        )

    def _on_step_skipped(self, event: ExecutionEvent) -> None:
        """Persist a step that will not run, with its reason."""
        name = event.step_name or ""
        self._stop_capture()
        reason = event.data.get("reason", "skipped")
        self._store.mark_step(self.run_id, name, StepState.SKIPPED, loop=self._loop)
        step_id = self._step_ids.get(name)
        if step_id:
            _broadcast_step_log(
                self.run_id, step_id, "info", f"Step {name}: skipped ({reason})", self._loop
            )

    def _on_visualization_failed(self, event: ExecutionEvent) -> None:
        """Surface a non-fatal visualization failure to the run's log stream."""
        name = event.step_name or ""
        step_id = self._step_ids.get(name)
        if step_id:
            _broadcast_step_log(
                self.run_id,
                step_id,
                "warning",
                f"Step {name}: visualization failed: {event.error}",
                self._loop,
            )

    # -- lifecycle ----------------------------------------------------------

    def close(self) -> None:
        """Detach any lingering log handler. Always called by the runner."""
        self._stop_capture()

    def _stop_capture(self) -> None:
        if self._capture is not None:
            self._capture.stop()
            self._capture = None


__all__ = [
    "RunEventSink",
    "RunStateStore",
    "schedule_broadcast",
]
