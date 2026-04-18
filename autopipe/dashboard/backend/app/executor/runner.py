"""Background task runner for executing autopipe pipelines.

Bridges the dashboard's Run/Step DB records with autopipe.core.Pipeline:
1. Loads a pipeline from config dict using autopipe's loader
2. Runs it in a background thread (Pipeline.run() is synchronous)
3. Updates DB run record with status, timestamps, metrics, errors
"""

import logging
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.models import Run, RunStatus

logger = logging.getLogger(__name__)

# Ensure autopipe is importable — add project root to sys.path
_PROJECT_ROOT = str(Path(__file__).resolve().parents[5])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Sync DB engine for background threads (can't use async engine from threads)
_sync_engine = None
_SyncSessionLocal = None


def _get_sync_session_factory() -> sessionmaker:
    """Get or create the sync session factory for background threads."""
    global _sync_engine, _SyncSessionLocal
    if _SyncSessionLocal is None:
        db_url = settings.DATABASE_URL
        # aiosqlite URL → sqlite for sync engine
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


def _run_pipeline_in_thread(run_id: str, pipeline_config: dict, initial_inputs: dict | None = None) -> None:
    """Execute a pipeline run in a background thread.

    Uses a sync DB session since we're outside the async event loop.
    """
    SessionLocal = _get_sync_session_factory()

    # Mark run as RUNNING
    with SessionLocal() as db:
        run = db.get(Run, run_id)
        if not run:
            logger.error(f"Run {run_id} not found, cannot execute")
            return
        run.status = RunStatus.RUNNING
        run.started_at = datetime.utcnow()
        db.commit()

    # Load pipeline from config
    try:
        pipeline = _load_pipeline(pipeline_config)
    except Exception as e:
        logger.error(f"Failed to load pipeline for run {run_id}: {e}")
        logger.error(traceback.format_exc())
        with SessionLocal() as db:
            run = db.get(Run, run_id)
            if run:
                run.status = RunStatus.FAILED
                run.error_message = f"Pipeline load error: {e}"
                run.completed_at = datetime.utcnow()
                db.commit()
        return

    # Execute pipeline (synchronous)
    try:
        outputs = pipeline.run(initial_inputs=initial_inputs)

        # Collect metrics from steps
        metrics = {}
        for step in pipeline.steps.values():
            if step.metrics:
                metrics[step.name] = step.metrics

        # Flatten top-level metrics for the run
        run_metrics = {}
        for name, vals in metrics.items():
            if isinstance(vals, dict):
                for k, v in vals.items():
                    run_metrics[f"{name}_{k}" if k != name else k] = v
            else:
                run_metrics[name] = vals

        with SessionLocal() as db:
            run = db.get(Run, run_id)
            if run:
                run.status = RunStatus.SUCCESS
                run.completed_at = datetime.utcnow()
                if run.started_at:
                    run.duration_seconds = (run.completed_at - run.started_at).total_seconds()
                if run_metrics:
                    run.metrics = run_metrics
                db.commit()

        logger.info(f"Run {run_id} completed successfully")

    except Exception as e:
        error_message = f"{type(e).__name__}: {e}"
        logger.error(f"Run {run_id} failed: {error_message}\n{traceback.format_exc()}")

        with SessionLocal() as db:
            run = db.get(Run, run_id)
            if run:
                run.status = RunStatus.FAILED
                run.error_message = error_message
                run.completed_at = datetime.utcnow()
                if run.started_at:
                    run.duration_seconds = (run.completed_at - run.started_at).total_seconds()
                db.commit()


async def execute_run(run_id: str, pipeline_config: dict, initial_inputs: dict | None = None) -> None:
    """Launch a pipeline run in a background thread.

    This is the async entry point called by FastAPI BackgroundTasks.
    It spawns a daemon thread that does the actual work synchronously.
    """
    thread = threading.Thread(
        target=_run_pipeline_in_thread,
        args=(run_id, pipeline_config, initial_inputs),
        daemon=True,
        name=f"pipeline-run-{run_id[:8]}",
    )
    thread.start()