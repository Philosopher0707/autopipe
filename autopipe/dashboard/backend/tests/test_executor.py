"""Integration tests for the pipeline executor."""

import uuid
from pathlib import Path

from app.db.models import (
    Base,
    DriftAlert,
    DriftReport,
    MetricLog,
    Pipeline,
    Run,
    RunStatus,
    Step,
    StepStatus,
)
from app.executor import runner
from app.executor.sink import RunStateStore
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from autopipe.core.run_state import StepState


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


def _basic_config() -> dict:
    return {
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


def test_prologue_register_failure_still_forces_terminal(tmp_path: Path, monkeypatch):
    """A registry failure in the prologue must not strand the run as PENDING."""
    SessionLocal = _make_sync_session(tmp_path / "test.db")
    _pipeline_id, run_id = _seed_pipeline_and_run(SessionLocal)
    monkeypatch.setattr(runner, "_SyncSessionLocal", SessionLocal)
    monkeypatch.setattr(runner, "_event_loop", None)

    def boom(*_args, **_kwargs):
        raise RuntimeError("registry unavailable")

    monkeypatch.setattr(runner, "register_run", boom)
    runner._run_pipeline_in_thread(run_id, _basic_config())

    with SessionLocal() as db:
        run = db.get(Run, run_id)
        assert run.status == RunStatus.FAILED
        assert run.error_message is not None


def test_cancel_before_register_is_honoured(tmp_path: Path, monkeypatch):
    """cancel_run before register queues a cancel; the run must end CANCELLED."""
    from app.executor.registry import cancel_run, unregister_run

    SessionLocal = _make_sync_session(tmp_path / "test.db")
    _pipeline_id, run_id = _seed_pipeline_and_run(SessionLocal)
    monkeypatch.setattr(runner, "_SyncSessionLocal", SessionLocal)
    monkeypatch.setattr(runner, "_event_loop", None)

    assert cancel_run(run_id) is False
    runner._run_pipeline_in_thread(run_id, _basic_config())

    with SessionLocal() as db:
        run = db.get(Run, run_id)
        assert run.status == RunStatus.CANCELLED
        steps = db.query(Step).filter(Step.run_id == run_id).all()
        assert steps
        assert all(s.status == StepStatus.SKIPPED for s in steps)
    unregister_run(run_id)


def test_sink_close_failure_still_finalizes(tmp_path: Path, monkeypatch):
    """RunEventSink.close raising must not prevent DB finalization."""
    SessionLocal = _make_sync_session(tmp_path / "test.db")
    _pipeline_id, run_id = _seed_pipeline_and_run(SessionLocal)
    monkeypatch.setattr(runner, "_SyncSessionLocal", SessionLocal)
    monkeypatch.setattr(runner, "_event_loop", None)
    from app.executor.sink import RunEventSink

    def boom(self):
        raise RuntimeError("ws sink closed unexpectedly")

    monkeypatch.setattr(RunEventSink, "close", boom)
    runner._run_pipeline_in_thread(run_id, _basic_config())

    with SessionLocal() as db:
        run = db.get(Run, run_id)
        assert run.status == RunStatus.SUCCESS


def test_finalize_failure_forces_terminal(tmp_path: Path, monkeypatch):
    """A raising finish_run must fall through to _force_terminal, not strand RUNNING."""
    SessionLocal = _make_sync_session(tmp_path / "test.db")
    _pipeline_id, run_id = _seed_pipeline_and_run(SessionLocal)
    monkeypatch.setattr(runner, "_SyncSessionLocal", SessionLocal)
    monkeypatch.setattr(runner, "_event_loop", None)
    from app.executor.sink import RunStateStore

    calls = {"n": 0}
    orig = RunStateStore.finish_run

    def flaky(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("disk full")
        return orig(self, *args, **kwargs)

    monkeypatch.setattr(RunStateStore, "finish_run", flaky)
    runner._run_pipeline_in_thread(run_id, _basic_config())

    with SessionLocal() as db:
        run = db.get(Run, run_id)
        assert run.status == RunStatus.FAILED
        assert run.error_message is not None


def test_shutdown_executor_cancels_and_sweeps(tmp_path: Path, monkeypatch):
    """shutdown_executor must cancel active runs and sweep to a terminal state."""
    import threading
    import time

    SessionLocal = _make_sync_session(tmp_path / "test.db")
    _pipeline_id, run_id = _seed_pipeline_and_run(SessionLocal)
    monkeypatch.setattr(runner, "_SyncSessionLocal", SessionLocal)
    monkeypatch.setattr(runner, "_event_loop", None)

    from autopipe.core.steps import PrintStep

    orig_run = PrintStep.run

    def slow_run(self, **kwargs):
        time.sleep(1.5)
        return orig_run(self, **kwargs)

    monkeypatch.setattr(PrintStep, "run", slow_run)

    t = threading.Thread(target=runner._run_pipeline_in_thread, args=(run_id, _basic_config()))
    runner._remember_thread(run_id, t)
    t.start()
    time.sleep(0.3)  # let it register and enter the step
    runner.shutdown_executor(timeout=0.05)
    t.join(timeout=5)
    assert not t.is_alive(), "worker thread did not exit after shutdown"

    with SessionLocal() as db:
        run = db.get(Run, run_id)
        assert run.status in (
            RunStatus.CANCELLED,
            RunStatus.FAILED,
            RunStatus.SUCCESS,
        )


def test_registry_pending_cancel_survives_until_register():
    """cancel_run on an unregistered id queues the cancel for later register_run."""
    from app.executor.registry import cancel_run, register_run, unregister_run

    rid = f"pending-{uuid.uuid4()}"
    assert cancel_run(rid) is False
    event = register_run(rid)
    assert event.is_set(), "queued cancel was lost before register"
    unregister_run(rid)


def test_mark_step_writes_metric_log_series(tmp_path: Path):
    """Numeric step metrics must land in MetricLog (the charts read path)."""
    SessionLocal = _make_sync_session(tmp_path / "metrics.db")
    _pipeline_id, run_id = _seed_pipeline_and_run(SessionLocal)
    store = RunStateStore(SessionLocal)

    store.mark_run_running(run_id)
    store.create_steps(run_id, ["step1"], {"step1": "print"})
    store.mark_step(run_id, "step1", StepState.RUNNING)
    store.mark_step(
        run_id,
        "step1",
        StepState.SUCCESS,
        metrics={"loss": 0.25, "accuracy": 0.9, "ok": True, "note": "skip"},
    )

    with SessionLocal() as db:
        rows = db.scalars(select(MetricLog).where(MetricLog.run_id == run_id)).all()
        assert len(rows) == 2, "only numeric non-bool metrics become series points"
        by_name = {r.metric_name: r for r in rows}
        assert by_name["loss"].value == 0.25
        assert by_name["accuracy"].value == 0.9
        step = db.scalars(select(Step).where(Step.run_id == run_id)).first()
        for r in rows:
            assert r.step_id == step.id
            assert r.step_index == step.order_index
            assert r.pipeline_id is not None


def test_mark_step_conflict_leaves_no_metric_logs(tmp_path: Path):
    """A CAS conflict rolls back the status write and the metric rows with it."""
    SessionLocal = _make_sync_session(tmp_path / "conflict.db")
    _pipeline_id, run_id = _seed_pipeline_and_run(SessionLocal)
    store = RunStateStore(SessionLocal)

    store.mark_run_running(run_id)
    store.create_steps(run_id, ["step1"], {"step1": "print"})
    store.mark_step(run_id, "step1", StepState.RUNNING)
    store.mark_step(run_id, "step1", StepState.SUCCESS, metrics={"first": 1.0})

    # A terminal step is immutable: SUCCESS -> FAILED must raise and write
    # nothing (the metric insert shares the rolled-back transaction).
    import pytest

    from autopipe.exceptions import StateTransitionError

    with pytest.raises(StateTransitionError):
        store.mark_step(run_id, "step1", StepState.FAILED, metrics={"second": 2.0})

    with SessionLocal() as db:
        rows = db.scalars(select(MetricLog).where(MetricLog.run_id == run_id)).all()
        assert [r.metric_name for r in rows] == ["first"]


def test_record_drift_persists_core_reports(tmp_path: Path):
    """Core DriftReport dataclasses land as a durable row + flagged-feature alerts."""
    from datetime import datetime, timezone

    from app.utils.drift_utils import normalize_feature_drifts

    from autopipe.monitoring.drift_detection import DriftReport as CoreDriftReport

    SessionLocal = _make_sync_session(tmp_path / "drift.db")
    _pipeline_id, run_id = _seed_pipeline_and_run(SessionLocal)
    store = RunStateStore(SessionLocal)

    now = datetime.now(timezone.utc)
    reports = [
        CoreDriftReport(
            timestamp=now,
            feature_name="x",
            drift_detected=True,
            metric_name="ks_statistic",
            metric_value=0.4,
            threshold=0.05,
            p_value=0.001,
        ),
        CoreDriftReport(
            timestamp=now,
            feature_name="y",
            drift_detected=False,
            metric_name="ks_statistic",
            metric_value=0.01,
            threshold=0.05,
            p_value=0.8,
        ),
    ]

    written = store.record_drift(run_id, {"detect": {"drift_reports": reports, "drift_ratio": 0.5}})
    assert written == 1
    assert store.record_drift(run_id, {"plain": {"message": "no reports"}}) == 0

    with SessionLocal() as db:
        row = db.scalars(select(DriftReport).where(DriftReport.run_id == run_id)).one()
        assert row.drift_detected is True
        assert row.drift_score == 0.5
        assert row.alert_generated is True
        assert set(row.feature_drifts) == {"x", "y"}
        # Core field names must round-trip through the read-path normalizer (G3).
        norm = normalize_feature_drifts(row.feature_drifts)
        assert norm["x"]["is_drifted"] is True
        assert norm["y"]["is_drifted"] is False
        alerts = db.scalars(select(DriftAlert).where(DriftAlert.drift_report_id == row.id)).all()
        assert [a.feature_name for a in alerts] == ["x"]
        assert alerts[0].drift_metric == "ks_statistic"
        assert alerts[0].drift_score == 0.4


def test_finalize_bridges_drift_outputs(tmp_path: Path, monkeypatch):
    """runner._finalize persists drift_reports from ExecutionResult.outputs."""
    from autopipe.core.execution import ExecutionResult
    from autopipe.core.run_state import RunState

    SessionLocal = _make_sync_session(tmp_path / "drift-fin.db")
    _pipeline_id, run_id = _seed_pipeline_and_run(SessionLocal)
    monkeypatch.setattr(runner, "_SyncSessionLocal", SessionLocal)
    monkeypatch.setattr(runner, "_event_loop", None)
    store = RunStateStore(SessionLocal)
    store.mark_run_running(run_id)

    result = ExecutionResult(
        run_id=run_id,
        pipeline_name="test-pipeline",
        state=RunState.SUCCESS,
        outputs={
            "detect": {
                "drift_reports": [
                    {
                        "feature_name": "f1",
                        "drift_detected": True,
                        "metric_name": "psi",
                        "metric_value": 0.3,
                        "threshold": 0.2,
                        "p_value": None,
                    }
                ],
                "drift_ratio": 1.0,
            }
        },
    )
    runner._finalize(run_id, result, store)

    with SessionLocal() as db:
        run = db.get(Run, run_id)
        assert run.status == RunStatus.SUCCESS
        row = db.scalars(select(DriftReport).where(DriftReport.run_id == run_id)).one()
        assert row.drift_detected is True
        assert "f1" in row.feature_drifts


def test_record_drift_finds_nested_dashboard_batches(tmp_path: Path):
    """DriftDashboardStep nests drift_reports under feature_drift — still bridged."""
    SessionLocal = _make_sync_session(tmp_path / "drift-nested.db")
    _pipeline_id, run_id = _seed_pipeline_and_run(SessionLocal)
    store = RunStateStore(SessionLocal)

    written = store.record_drift(
        run_id,
        {
            "dash": {
                "feature_drift": {
                    "drift_reports": [
                        {
                            "feature_name": "a",
                            "drift_detected": False,
                            "metric_name": "ks",
                            "metric_value": 0.01,
                            "threshold": 0.05,
                            "p_value": 0.9,
                        }
                    ],
                    "drift_ratio": 0.0,
                    "drift_detected_count": 0,
                },
                "summary": {"n_features": 1},
            }
        },
    )
    assert written == 1
    with SessionLocal() as db:
        row = db.scalars(select(DriftReport).where(DriftReport.run_id == run_id)).one()
        assert row.drift_score == 0.0
        assert row.drift_detected is False
        assert "a" in row.feature_drifts
        assert (
            db.scalars(select(DriftAlert).where(DriftAlert.drift_report_id == row.id)).all() == []
        )


def test_record_drift_tolerates_malformed_and_empty_payloads(tmp_path: Path):
    SessionLocal = _make_sync_session(tmp_path / "drift-junk.db")
    _pipeline_id, run_id = _seed_pipeline_and_run(SessionLocal)
    store = RunStateStore(SessionLocal)

    assert store.record_drift(run_id, None) == 0
    assert store.record_drift(run_id, {}) == 0
    # Batch whose entries lack feature_name / to_dict: skipped, no rows, no raise.
    assert (
        store.record_drift(
            run_id,
            {
                "detect": {
                    "drift_reports": [object(), {"metric_name": "psi"}, None],
                    "drift_ratio": 1.0,
                }
            },
        )
        == 0
    )
    with SessionLocal() as db:
        assert db.scalars(select(DriftReport).where(DriftReport.run_id == run_id)).all() == []


def test_finalize_survives_drift_persistence_failure(tmp_path: Path, monkeypatch):
    """A record_drift blow-up must not block the terminal write (I11)."""
    from autopipe.core.execution import ExecutionResult
    from autopipe.core.run_state import RunState

    SessionLocal = _make_sync_session(tmp_path / "drift-fail.db")
    _pipeline_id, run_id = _seed_pipeline_and_run(SessionLocal)
    monkeypatch.setattr(runner, "_SyncSessionLocal", SessionLocal)
    monkeypatch.setattr(runner, "_event_loop", None)
    store = RunStateStore(SessionLocal)
    store.mark_run_running(run_id)

    def boom(run_id_arg, outputs):
        raise RuntimeError("drift store down")

    monkeypatch.setattr(store, "record_drift", boom)
    result = ExecutionResult(
        run_id=run_id,
        pipeline_name="test-pipeline",
        state=RunState.SUCCESS,
        outputs={"detect": {"drift_reports": [{"feature_name": "x"}], "drift_ratio": 1.0}},
    )
    runner._finalize(run_id, result, store)

    with SessionLocal() as db:
        run = db.get(Run, run_id)
        assert run.status == RunStatus.SUCCESS
        assert db.scalars(select(DriftReport).where(DriftReport.run_id == run_id)).all() == []
