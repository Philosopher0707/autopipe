"""Integration tests for the pipeline executor."""

import uuid
from pathlib import Path

from app.db.models import Base, Pipeline, Run, RunStatus, Step, StepStatus
from app.executor import runner
from sqlalchemy import create_engine
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
