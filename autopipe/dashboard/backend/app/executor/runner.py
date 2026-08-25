"""Background task runner for executing autopipe pipelines.

Bridges the dashboard's Run/Step DB records with autopipe.core.Pipeline:
1. Loads a pipeline from config dict using autopipe's loader
2. Runs it step-by-step in a background thread
3. Creates/updates Step DB records with status, timestamps, metrics
4. Broadcasts status changes via WebSocket in real time
5. Updates DB run record with final status, timestamps, metrics, errors
"""

import asyncio
import logging
import sys
import threading
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.db.models import Run, RunStatus, Step, StepStatus
from app.executor.registry import register_run, unregister_run
from app.utils.datetime_utils import safe_duration_seconds
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None

logger = logging.getLogger(__name__)

# Ensure autopipe is importable — add project root to sys.path
_PROJECT_ROOT = str(Path(__file__).resolve().parents[5])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Sync DB engine for background threads (can't use async engine from threads)
_sync_engine = None
_SyncSessionLocal = None
_sync_engine_lock = threading.Lock()

# Reference to the running event loop for scheduling async broadcasts
_event_loop: asyncio.AbstractEventLoop | None = None


def set_event_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Store the event loop reference for async broadcasts from threads."""
    global _event_loop
    _event_loop = loop


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
        _SyncSessionLocal = sessionmaker(_sync_engine, expire_on_commit=False)
        return _SyncSessionLocal


def _load_pipeline(config: dict):
    """Load a Pipeline from a config dict using autopipe's loader."""
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)
    from autopipe.core.loader import load_pipeline_from_config

    return load_pipeline_from_config(config)


def _schedule_async(coro):
    """Schedule an async coroutine on the event loop from a sync thread."""
    if _event_loop is None or _event_loop.is_closed():
        return
    try:
        asyncio.run_coroutine_threadsafe(coro, _event_loop)
    except RuntimeError:
        logger.debug("Failed to schedule async coroutine", exc_info=True)


def _broadcast_run_status(run_id: str, status: str, data: dict | None = None) -> None:
    """Broadcast a run status change via WebSocket."""
    from app.api.v1.endpoints.websocket import broadcast_run_status

    _schedule_async(broadcast_run_status(run_id, status, data))


def _broadcast_step_status(run_id: str, step_id: str, step_name: str, status: str) -> None:
    """Broadcast a step status change via WebSocket as a run.log event."""
    from app.api.v1.endpoints.websocket import broadcast_run_log

    _schedule_async(broadcast_run_log(run_id, step_id, "info", f"Step {step_name}: {status}"))


def _broadcast_step_metric(run_id: str, step_id: str, metric_name: str, value: float) -> None:
    """Broadcast a step metric via WebSocket."""
    from app.api.v1.endpoints.websocket import broadcast_run_metric

    _schedule_async(broadcast_run_metric(run_id, step_id, metric_name, value))


class _WebSocketLogHandler(logging.Handler):
    """Captures Python log records during step execution and broadcasts them."""

    def __init__(self, run_id: str, step_id: str):
        super().__init__()
        self.run_id = run_id
        self.step_id = step_id

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            _broadcast_step_status(self.run_id, self.step_id, "", f"[{record.levelname}] {msg}")
        except Exception:
            logger.debug("WebSocket log broadcast failed", exc_info=True)


def _update_run_status(
    db: Session,
    run_id: str,
    status: RunStatus,
    error_message: str | None = None,
    metrics: dict | None = None,
) -> None:
    """Update run status and timestamps in the DB."""
    run = db.get(Run, run_id)
    if not run:
        return
    run.status = status
    if status == RunStatus.RUNNING and not run.started_at:
        run.started_at = datetime.now(timezone.utc)
    if status in (RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.CANCELLED):
        run.completed_at = datetime.now(timezone.utc)
        if run.started_at:
            run.duration_seconds = safe_duration_seconds(run.started_at, run.completed_at)
    if error_message:
        run.error_message = error_message
    if metrics:
        run.metrics = metrics
    db.commit()

    # Broadcast status change
    status_str = status.value if hasattr(status, "value") else str(status)
    data: dict = {}
    if error_message:
        data["error_message"] = error_message
    if metrics:
        data["metrics"] = metrics
    _broadcast_run_status(run_id, status_str, data)


def _update_step_status(
    db: Session,
    step_id: str,
    status: StepStatus,
    run_id: str = "",
    step_name: str = "",
    metrics: dict | None = None,
    error_message: str | None = None,
    duration_seconds: float | None = None,
) -> None:
    """Update step status and timestamps in the DB + broadcast."""
    step = db.get(Step, step_id)
    if not step:
        return
    step.status = status
    if status == StepStatus.RUNNING and not step.started_at:
        step.started_at = datetime.now(timezone.utc)
    if status == StepStatus.SUCCESS:
        step.completed_at = datetime.now(timezone.utc)
        if step.started_at:
            step.duration_seconds = safe_duration_seconds(step.started_at, step.completed_at)
    if status == StepStatus.FAILED:
        step.error_message = error_message
    if metrics:
        step.metrics = metrics
    if duration_seconds is not None:
        step.duration_seconds = duration_seconds
    db.commit()

    # Broadcast step status change
    if run_id:
        status_str = status.value if hasattr(status, "value") else str(status)
        _broadcast_step_status(run_id, step_id, step_name, status_str)

        # Broadcast individual metrics
        if metrics and status == StepStatus.SUCCESS:
            for metric_name, value in metrics.items():
                if isinstance(value, (int, float)):
                    _broadcast_step_metric(run_id, step_id, metric_name, float(value))


def _build_step_inputs(core_step, outputs: dict, initial_inputs: dict | None) -> dict:
    """Build inputs for a step from dependency outputs or initial inputs."""
    if core_step.depends_on:
        return {dep: outputs[dep] for dep in core_step.depends_on if dep in outputs}
    return dict(initial_inputs or {})


def _try_visualize(core_step, inputs: dict) -> None:
    """Attempt to visualize step output; non-critical."""
    try:
        core_step.visualize(**inputs)
    except Exception:
        logger.debug("Step visualization failed", exc_info=True)


def _collect_run_metrics(pipeline, execution_order: list) -> dict:
    """Collect run-level metrics from all step metrics."""
    run_metrics: dict = {}
    for step_name in execution_order:
        core_step = pipeline.steps[step_name]
        if core_step.metrics:
            for k, v in core_step.metrics.items():
                run_metrics[f"{step_name}_{k}" if k != step_name else k] = v
    return run_metrics


def _collect_system_metrics() -> dict:
    """Collect CPU and memory usage via psutil."""
    metrics: dict = {}
    if not psutil:
        return metrics

    try:
        metrics["cpu_percent"] = round(psutil.cpu_percent(interval=0.1), 1)
        metrics["memory_percent"] = round(psutil.virtual_memory().percent, 1)
    except Exception:
        logger.debug("psutil CPU/memory metrics failed", exc_info=True)

    return metrics


def _finalize_run(
    SessionLocal: sessionmaker,
    run_id: str,
    pipeline,
    execution_order: list,
    cancelled: bool,
    run_failed: bool,
    failed_step_name: str | None,
) -> None:
    """Update final run status and metrics."""
    with SessionLocal() as db:
        if cancelled:
            _update_run_status(
                db, run_id, RunStatus.CANCELLED, error_message="Run cancelled by user"
            )
        elif run_failed:
            error_msg = (
                f"Step '{failed_step_name}' failed" if failed_step_name else "Pipeline failed"
            )
            _update_run_status(db, run_id, RunStatus.FAILED, error_message=error_msg)
        else:
            run_metrics = _collect_run_metrics(pipeline, execution_order)
            run_metrics.update(_collect_system_metrics())
            _update_run_status(db, run_id, RunStatus.SUCCESS, metrics=run_metrics or None)


def _mark_step_skipped(
    SessionLocal: sessionmaker, step_id: str, run_id: str, step_name: str
) -> None:
    """Mark a single step as SKIPPED and broadcast."""
    with SessionLocal() as db:
        _update_step_status(db, step_id, StepStatus.SKIPPED, run_id=run_id, step_name=step_name)


def _mark_remaining_skipped(
    SessionLocal: sessionmaker,
    execution_order: list,
    step_id_map: dict,
    run_id: str,
    from_step_name: str,
) -> None:
    """Mark remaining steps after `from_step_name` as SKIPPED."""
    idx = execution_order.index(from_step_name) + 1
    for remaining in execution_order[idx:]:
        _mark_step_skipped(SessionLocal, step_id_map[remaining], run_id, remaining)


class _LogCapture:
    """Context manager that attaches a WebSocket log handler for the duration."""

    def __init__(self, run_id: str, step_id: str):
        self.handler = _WebSocketLogHandler(run_id, step_id)
        self.handler.setLevel(logging.DEBUG)
        self.logger = logging.getLogger("autopipe")

    def __enter__(self):
        self.logger.addHandler(self.handler)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.removeHandler(self.handler)
        return False


def _run_pipeline_in_thread(
    run_id: str, pipeline_config: dict, initial_inputs: dict | None = None
) -> None:
    """Execute a pipeline run in a background thread with step-level tracking."""
    SessionLocal = _get_sync_session_factory()

    # Register run for cancellation tracking
    cancel_event = register_run(run_id)

    try:
        # Mark run as RUNNING
        with SessionLocal() as db:
            run = db.get(Run, run_id)
            if not run:
                logger.error("Run %s not found, cannot execute", run_id)
                return
            run.status = RunStatus.RUNNING
            run.started_at = datetime.now(timezone.utc)
            db.commit()

        _broadcast_run_status(run_id, "running")

        # Load pipeline from config
        try:
            pipeline = _load_pipeline(pipeline_config)
        except Exception as e:
            logger.error("Failed to load pipeline for run %s: %s", run_id, e)
            logger.error(traceback.format_exc())
            with SessionLocal() as db:
                _update_run_status(
                    db, run_id, RunStatus.FAILED, error_message=f"Pipeline load error: {e}"
                )
            return

        # Resolve execution order
        try:
            execution_order = pipeline.execution_order
        except ValueError as e:
            logger.error("Pipeline has cycle or invalid deps for run %s: %s", run_id, e)
            with SessionLocal() as db:
                _update_run_status(db, run_id, RunStatus.FAILED, error_message=str(e))
            return

        # Create Step DB records (PENDING)
        step_id_map: dict = {}
        with SessionLocal() as db:
            for i, step_name in enumerate(execution_order):
                core_step = pipeline.steps[step_name]
                db_step = Step(
                    id=str(uuid.uuid4()),
                    run_id=run_id,
                    name=step_name,
                    step_type=type(core_step).__name__,
                    status=StepStatus.PENDING,
                    order_index=i,
                )
                db.add(db_step)
                db.flush()
                step_id_map[step_name] = db_step.id
            db.commit()

        # Execute pipeline step-by-step
        outputs = dict(initial_inputs or {})
        run_failed = False
        failed_step_name = None
        cancelled = False

        for step_name in execution_order:
            # Check for cancellation between steps
            if cancel_event.is_set():
                cancelled = True
                _mark_step_skipped(SessionLocal, step_id_map[step_name], run_id, step_name)
                _mark_remaining_skipped(
                    SessionLocal, execution_order, step_id_map, run_id, step_name
                )
                break

            if run_failed:
                _mark_step_skipped(SessionLocal, step_id_map[step_name], run_id, step_name)
                continue

            core_step = pipeline.steps[step_name]
            step_id = step_id_map[step_name]

            # Mark step as RUNNING
            with SessionLocal() as db:
                _update_step_status(
                    db, step_id, StepStatus.RUNNING, run_id=run_id, step_name=step_name
                )

            # Build inputs and execute
            inputs = _build_step_inputs(core_step, outputs, initial_inputs)

            with _LogCapture(run_id, step_id):
                try:
                    step_output = core_step.run(**inputs)
                    outputs[step_name] = step_output

                    step_metrics = dict(core_step.metrics) if core_step.metrics else None
                    _try_visualize(core_step, inputs)

                    with SessionLocal() as db:
                        _update_step_status(
                            db,
                            step_id,
                            StepStatus.SUCCESS,
                            metrics=step_metrics,
                            run_id=run_id,
                            step_name=step_name,
                        )

                except Exception as e:
                    step_error = f"{type(e).__name__}: {e}"
                    logger.error("Step %s failed for run %s: %s", step_name, run_id, step_error)
                    run_failed = True
                    failed_step_name = step_name

                    with SessionLocal() as db:
                        _update_step_status(
                            db,
                            step_id,
                            StepStatus.FAILED,
                            error_message=step_error,
                            run_id=run_id,
                            step_name=step_name,
                        )

        # Finalize run status
        _finalize_run(
            SessionLocal, run_id, pipeline, execution_order, cancelled, run_failed, failed_step_name
        )

        logger.info(
            "Run %s %s",
            run_id,
            "cancelled" if cancelled else "failed" if run_failed else "completed successfully",
        )
    finally:
        # Always unregister the run
        unregister_run(run_id)


async def execute_run(
    run_id: str, pipeline_config: dict, initial_inputs: dict | None = None
) -> None:
    """Launch a pipeline run in a background thread.

    This is the async entry point called by FastAPI BackgroundTasks.
    It captures the current event loop for WebSocket broadcasts,
    then spawns a daemon thread for the actual work.
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
    thread.start()
