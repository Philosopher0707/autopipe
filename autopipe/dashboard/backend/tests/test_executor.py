"""Integration tests for the pipeline executor."""

import uuid
from pathlib import Path

from app.db.models import Base, Pipeline, Run, RunStatus, Step, StepStatus
from app.executor import runner
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


def _make_sync_session(db_path: Path) -> sessionmaker:
    """Create a sync session factory for a temp SQLite DB."""
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def _seed_pipeline_and_run(SessionLocal: sessionmaker) -> tuple:
    """Insert a Pipeline and Run record, return their IDs."""
    pipeline_config = {
        "name": "test-pipeline",
        "steps": [
            {
                "name": "step1",
                "type": "autopipe.core.steps.PrintStep",
                "params": {"message": "hello"},
            },
            {
                "name": "step2",
                "type": "autopipe.core.steps.PrintStep",
                "depends_on": ["step1"],
                "params": {"message": "world"},
            },
        ],
    }

    with SessionLocal() as db:
        pipeline = Pipeline(
            id=str(uuid.uuid4()),
            name="test-pipeline",
            config=pipeline_config,
        )
        db.add(pipeline)
        db.commit()

        run = Run(
            id=str(uuid.uuid4()),
            pipeline_id=pipeline.id,
            status=RunStatus.PENDING,
            config=pipeline_config,
        )
        db.add(run)
        db.commit()
        return pipeline.id, run.id


def test_run_pipeline_in_thread_success(tmp_path: Path):
    """Executor should complete a simple pipeline and update DB records."""
    db_file = tmp_path / "test.db"
    SessionLocal = _make_sync_session(db_file)

    # Patch executor to use our test DB
    original_local = runner._SyncSessionLocal
    runner._SyncSessionLocal = SessionLocal

    # Disable WebSocket broadcasts (no event loop in test)
    original_loop = runner._event_loop
    runner._event_loop = None

    try:
        _pipeline_id, run_id = _seed_pipeline_and_run(SessionLocal)

        pipeline_config = {
            "name": "test-pipeline",
            "steps": [
                {
                    "name": "step1",
                    "type": "autopipe.core.steps.PrintStep",
                    "params": {"message": "hello"},
                },
                {
                    "name": "step2",
                    "type": "autopipe.core.steps.PrintStep",
                    "depends_on": ["step1"],
                    "params": {"message": "world"},
                },
            ],
        }

        runner._run_pipeline_in_thread(run_id, pipeline_config)

        # Verify run status
        with SessionLocal() as db:
            run = db.get(Run, run_id)
            assert run is not None
            assert run.status == RunStatus.SUCCESS
            assert run.started_at is not None
            assert run.completed_at is not None
            assert run.duration_seconds is not None
            assert run.metrics is not None
            assert "cpu_percent" in run.metrics or "memory_percent" in run.metrics

            # Verify steps were created
            steps = db.query(Step).filter(Step.run_id == run_id).order_by(Step.order_index).all()
            assert len(steps) == 2
            assert steps[0].name == "step1"
            assert steps[0].status == StepStatus.SUCCESS
            assert steps[0].started_at is not None
            assert steps[0].completed_at is not None
            assert steps[1].name == "step2"
            assert steps[1].status == StepStatus.SUCCESS

    finally:
        runner._SyncSessionLocal = original_local
        runner._event_loop = original_loop


def test_run_pipeline_in_thread_failure(tmp_path: Path, monkeypatch):
    """Executor should mark a run FAILED when a step raises."""
    db_file = tmp_path / "test.db"
    SessionLocal = _make_sync_session(db_file)

    original_local = runner._SyncSessionLocal
    runner._SyncSessionLocal = SessionLocal
    original_loop = runner._event_loop
    runner._event_loop = None

    try:
        _pipeline_id, run_id = _seed_pipeline_and_run(SessionLocal)

        # Monkeypatch PrintStep to raise on the second step
        from autopipe.core.steps import PrintStep

        original_run = PrintStep.run

        def _failing_run(self, **kwargs):
            if self.name == "fail_step":
                raise RuntimeError("simulated failure")
            return original_run(self, **kwargs)

        monkeypatch.setattr(PrintStep, "run", _failing_run)

        pipeline_config = {
            "name": "test-pipeline",
            "steps": [
                {
                    "name": "step1",
                    "type": "autopipe.core.steps.PrintStep",
                    "params": {"message": "hello"},
                },
                {
                    "name": "fail_step",
                    "type": "autopipe.core.steps.PrintStep",
                    "depends_on": ["step1"],
                },
                {
                    "name": "step3",
                    "type": "autopipe.core.steps.PrintStep",
                    "depends_on": ["fail_step"],
                },
            ],
        }

        runner._run_pipeline_in_thread(run_id, pipeline_config)

        with SessionLocal() as db:
            run = db.get(Run, run_id)
            assert run.status == RunStatus.FAILED
            assert "fail_step" in run.error_message

            steps = db.query(Step).filter(Step.run_id == run_id).order_by(Step.order_index).all()
            assert len(steps) == 3
            assert steps[0].status == StepStatus.SUCCESS
            assert steps[1].status == StepStatus.FAILED
            assert steps[2].status == StepStatus.SKIPPED

    finally:
        runner._SyncSessionLocal = original_local
        runner._event_loop = original_loop


def test_run_pipeline_in_thread_cancellation(tmp_path: Path, monkeypatch):
    """Executor should mark remaining steps SKIPPED when cancelled."""
    import threading

    db_file = tmp_path / "test.db"
    SessionLocal = _make_sync_session(db_file)

    original_local = runner._SyncSessionLocal
    runner._SyncSessionLocal = SessionLocal
    original_loop = runner._event_loop
    runner._event_loop = None

    try:
        _pipeline_id, run_id = _seed_pipeline_and_run(SessionLocal)

        pipeline_config = {
            "name": "test-pipeline",
            "steps": [
                {
                    "name": "step1",
                    "type": "autopipe.core.steps.PrintStep",
                    "params": {"message": "hello"},
                },
                {"name": "step2", "type": "autopipe.core.steps.PrintStep", "depends_on": ["step1"]},
                {"name": "step3", "type": "autopipe.core.steps.PrintStep", "depends_on": ["step2"]},
            ],
        }

        # Monkeypatch register_run to return a pre-set cancellation event
        pre_set_event = threading.Event()
        pre_set_event.set()
        monkeypatch.setattr(runner, "register_run", lambda _run_id: pre_set_event)

        runner._run_pipeline_in_thread(run_id, pipeline_config)

        with SessionLocal() as db:
            run = db.get(Run, run_id)
            assert run.status == RunStatus.CANCELLED

            steps = db.query(Step).filter(Step.run_id == run_id).order_by(Step.order_index).all()
            assert len(steps) == 3
            assert steps[0].status == StepStatus.SKIPPED
            assert steps[1].status == StepStatus.SKIPPED
            assert steps[2].status == StepStatus.SKIPPED

    finally:
        runner._SyncSessionLocal = original_local
        runner._event_loop = original_loop
        runner.unregister_run(run_id)


def test_sweep_orphaned_runs_marks_stale_running_failed(tmp_path: Path):
    """Runs/Steps left RUNNING or PENDING by a dead process become FAILED at startup."""

    SessionLocal = _make_sync_session(tmp_path / "sweep.db")
    _, run_id = _seed_pipeline_and_run(SessionLocal)

    with SessionLocal() as db:
        run = db.get(Run, run_id)
        run.status = RunStatus.RUNNING
        step = Step(
            id=str(uuid.uuid4()),
            run_id=run_id,
            name="step1",
            step_type="PrintStep",
            status=StepStatus.RUNNING,
            order_index=0,
        )
        db.add(step)
        db.commit()

    # The function reads the module-level session factory; point it at tmp DB.
    import app.executor.runner as runner_mod

    original = runner_mod._get_sync_session_factory
    runner_mod._get_sync_session_factory = lambda: SessionLocal
    try:
        swept = runner_mod.sweep_orphaned_runs()
    finally:
        runner_mod._get_sync_session_factory = original

    assert swept == 1
    with SessionLocal() as db:
        assert db.get(Run, run_id).status == RunStatus.FAILED
        step_row = db.scalars(select(Step).where(Step.run_id == run_id)).first()
        assert step_row is not None and step_row.status == StepStatus.FAILED


def test_sweep_orphaned_runs_marks_stale_pending_failed(tmp_path: Path):
    """PENDING runs whose BackgroundTasks died with the process are failed (I12)."""

    SessionLocal = _make_sync_session(tmp_path / "sweep_pending.db")
    _, run_id = _seed_pipeline_and_run(SessionLocal)

    with SessionLocal() as db:
        run = db.get(Run, run_id)
        run.status = RunStatus.PENDING
        db.commit()

    import app.executor.runner as runner_mod

    original = runner_mod._get_sync_session_factory
    runner_mod._get_sync_session_factory = lambda: SessionLocal
    try:
        swept = runner_mod.sweep_orphaned_runs()
    finally:
        runner_mod._get_sync_session_factory = original

    assert swept == 1
    with SessionLocal() as db:
        assert db.get(Run, run_id).status == RunStatus.FAILED


def test_log_handler_filters_other_runs():
    """A handler attached for run A must drop records emitted under run B."""
    import logging as _logging

    from app.executor.runner import _current_run_id, _WebSocketLogHandler

    handler = _WebSocketLogHandler(run_id="run-a", step_id="step-a")
    record = _logging.LogRecord("autopipe", _logging.INFO, __file__, 1, "msg", None, None)

    token = _current_run_id.set("run-b")
    try:
        assert handler.filter(record) is False, "run-B record leaked into run-A stream"
    finally:
        _current_run_id.reset(token)

    token = _current_run_id.set("run-a")
    try:
        assert handler.filter(record) is True
    finally:
        _current_run_id.reset(token)
