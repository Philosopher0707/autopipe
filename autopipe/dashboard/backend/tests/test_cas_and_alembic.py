"""M2: compare-and-swap status writes, sweep gating, alembic drift."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from app.core.config import settings
from app.db.models import Base, Pipeline, Run, RunStatus, Step, StepStatus
from app.executor.sink import RunStateStore, _cas_run_status, _cas_step_status, _conflict_error
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from autopipe.core.run_state import RunState, StepState
from autopipe.exceptions import StateTransitionError

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _make_store(tmp_path: Path) -> tuple[sessionmaker, RunStateStore]:
    engine = create_engine(f"sqlite:///{tmp_path / 'cas.db'}", echo=False)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    return factory, RunStateStore(factory)


def _seed(factory: sessionmaker) -> tuple[str, str]:
    with factory() as db:
        pipeline = Pipeline(id="p1", name="p", config={"steps": []})
        run = Run(id="r1", pipeline_id="p1", status=RunStatus.PENDING, config={"steps": []})
        db.add_all([pipeline, run])
        db.commit()
        return pipeline.id, run.id


def test_finish_run_cas_rejects_stale_expected(tmp_path: Path):
    """finish_run must not clobber a status that changed after the read."""
    factory, _store = _make_store(tmp_path)
    _seed(factory)

    # Simulate a concurrent writer moving PENDING -> RUNNING between read and write.
    with factory() as db:
        db.query(Run).filter(Run.id == "r1").update({"status": RunStatus.RUNNING})
        db.commit()

    with factory() as db:
        run = db.get(Run, "r1")
        assert run.status == RunStatus.RUNNING
        ok = _cas_run_status(db, "r1", RunStatus.PENDING, RunState.SUCCESS)
        assert ok is False
        db.rollback()

    with factory() as db:
        assert db.get(Run, "r1").status == RunStatus.RUNNING


def test_finish_run_cas_succeeds_on_matching_expected(tmp_path: Path):
    """When the row still has the expected status, the CAS write lands."""
    factory, store = _make_store(tmp_path)
    _seed(factory)
    assert store.mark_run_running("r1") is True
    assert store.finish_run("r1", RunState.FAILED, error="boom") is True
    with factory() as db:
        run = db.get(Run, "r1")
        assert run.status == RunStatus.FAILED
        assert run.error_message == "boom"


def test_finish_run_idempotent_when_already_terminal(tmp_path: Path):
    """A second finish_run for the same terminal state is a no-op success."""
    factory, store = _make_store(tmp_path)
    _seed(factory)
    store.mark_run_running("r1")
    assert store.finish_run("r1", RunState.SUCCESS) is True
    assert store.finish_run("r1", RunState.SUCCESS) is True


def test_mark_step_cas_rejects_stale_expected(tmp_path: Path):
    """mark_step must not overwrite a step whose status moved concurrently."""
    factory, _store = _make_store(tmp_path)
    _seed(factory)
    with factory() as db:
        step = Step(
            id="s1",
            run_id="r1",
            name="step1",
            step_type="print",
            status=StepStatus.RUNNING,
            order_index=0,
        )
        db.add(step)
        db.commit()

    with factory() as db:
        ok = _cas_step_status(db, "s1", StepStatus.PENDING, StepState.SUCCESS)
        assert ok is False
        db.rollback()

    with factory() as db:
        assert db.get(Step, "s1").status == StepStatus.RUNNING


def test_sweep_uses_ensure_transition_and_skips_terminal(tmp_path: Path):
    """Sweep only touches non-terminal rows and goes through the gate."""
    factory, store = _make_store(tmp_path)
    _seed(factory)
    with factory() as db:
        db.query(Run).filter(Run.id == "r1").update({"status": RunStatus.RUNNING})
        terminal = Run(
            id="r2",
            pipeline_id="p1",
            status=RunStatus.SUCCESS,
            config={"steps": []},
        )
        db.add(terminal)
        db.commit()

    swept = store.sweep_orphaned()
    assert swept == 1
    with factory() as db:
        assert db.get(Run, "r1").status == RunStatus.FAILED
        assert db.get(Run, "r1").error_message == "Interrupted by server restart"
        assert db.get(Run, "r2").status == RunStatus.SUCCESS


def test_conflict_error_carries_context():
    err = _conflict_error("run=x", "pending", "running")
    assert isinstance(err, StateTransitionError)
    assert "run=x" in str(err)
    assert err.details["expected"] == "pending"
    assert err.details["actual"] == "running"


def _upgrade_alembic(db_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{db_path}")
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(cfg, "head")


def test_alembic_fresh_db_matches_create_all(tmp_path: Path, monkeypatch):
    """A DB built by `alembic upgrade head` must match `create_all` (no drift)."""
    alembic_db = tmp_path / "alembic.db"
    create_all_db = tmp_path / "create_all.db"

    _upgrade_alembic(alembic_db, monkeypatch)

    engine_a = create_engine(f"sqlite:///{alembic_db}")
    engine_c = create_engine(f"sqlite:///{create_all_db}")
    Base.metadata.create_all(engine_c)

    def schema(engine):
        insp = inspect(engine)
        tables = {}
        for name in sorted(insp.get_table_names()):
            if name == "alembic_version":  # alembic's own bookkeeping, not app schema
                continue
            cols = {c["name"]: str(c["type"]) for c in insp.get_columns(name)}
            tables[name] = cols
        return tables

    assert schema(engine_a) == schema(engine_c)


def test_alembic_stamped_db_is_usable_end_to_end(tmp_path: Path, monkeypatch):
    """App models must work against a DB created only by alembic (no create_all)."""
    db_path = tmp_path / "e2e.db"
    _upgrade_alembic(db_path, monkeypatch)

    engine = create_engine(f"sqlite:///{db_path}")
    factory = sessionmaker(engine, expire_on_commit=False)
    store = RunStateStore(factory)

    with factory() as db:
        db.add(Pipeline(id="p1", name="p", config={"steps": []}))
        db.add(Run(id="r1", pipeline_id="p1", status=RunStatus.PENDING, config={"steps": []}))
        db.commit()

    assert store.mark_run_running("r1") is True
    assert store.finish_run("r1", RunState.SUCCESS) is True
    with factory() as db:
        assert db.get(Run, "r1").status == RunStatus.SUCCESS
