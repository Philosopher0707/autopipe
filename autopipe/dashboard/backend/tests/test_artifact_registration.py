"""Phase B: produced files become registered Artifact rows (one canonical writer).

REGISTERED (producers call record_produced_file):
  - ChartGenerator._save_fig — every chart PNG from VisualizationStep.run and
    every step visualize that uses ChartGenerator (data, deep_learning, core).
  - explainability direct writes (SHAP/LIME/HTML/PDP/permutation/feature/attention)
  - cross_validation visualize PNGs (cv_results/splits/bootstrap)
  - drift_detection visualize PNGs + DriftDashboardStep markdown report
  - SklearnTrainerStep save_path joblib dump

NOT registered (honest ceiling, documented in PROVENANCE_MODEL):
  - deep_learning Keras checkpoint files (async callback-chosen names)
  - model_registry saves (separate Python library registry; run-linkage is its
    own gap)
  - experiments/reporting, CLI/REPL exports (not on the run path)
"""

import hashlib
import os
from pathlib import Path
from uuid import uuid4

from app.db.models import Artifact, Base, Pipeline, Run, RunStatus
from app.executor import runner
from app.executor.sink import RunStateStore
from httpx import AsyncClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker


def _make_sync_session(db_path: Path) -> sessionmaker:
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def _seed_run(SessionLocal: sessionmaker) -> str:
    with SessionLocal() as db:
        pipeline = Pipeline(id=str(uuid4()), name="p", config={"steps": []})
        db.add(pipeline)
        db.commit()
        run = Run(
            id=str(uuid4()),
            pipeline_id=pipeline.id,
            status=RunStatus.RUNNING,
            config={"steps": []},
            config_hash=None,
            run_number=1,
        )
        db.add(run)
        db.commit()
        return run.id


def _write(path: Path, payload: bytes = b"artifact-bytes") -> str:
    path.write_bytes(payload)
    return str(path)


class TestRegisterArtifacts:
    def test_registers_file_with_content_hash_and_size(self, tmp_path: Path):
        SessionLocal = _make_sync_session(tmp_path / "reg.db")
        run_id = _seed_run(SessionLocal)
        store = RunStateStore(SessionLocal)
        payload = b"hello-artifact"
        path = _write(tmp_path / "model.pkl", payload)

        written = store.register_artifacts(run_id, [path])
        assert written == 1

        with SessionLocal() as db:
            row = db.scalars(select(Artifact).where(Artifact.run_id == run_id)).one()
            assert row.name == "model.pkl"
            assert row.artifact_type == "model"
            assert row.file_size == len(payload)
            assert row.sha256 == hashlib.sha256(payload).hexdigest()
            assert os.path.isabs(row.file_path)

    def test_artifact_type_inference(self, tmp_path: Path):
        SessionLocal = _make_sync_session(tmp_path / "types.db")
        run_id = _seed_run(SessionLocal)
        store = RunStateStore(SessionLocal)
        paths = [
            _write(tmp_path / "a.png"),
            _write(tmp_path / "b.html"),
            _write(tmp_path / "c.csv"),
            _write(tmp_path / "d.pkl"),
            _write(tmp_path / "e.unknown"),
        ]
        assert store.register_artifacts(run_id, paths) == 5
        with SessionLocal() as db:
            types = {
                r.name: r.artifact_type
                for r in db.scalars(select(Artifact).where(Artifact.run_id == run_id))
            }
        assert types == {
            "a.png": "plot",
            "b.html": "plot",
            "c.csv": "data",
            "d.pkl": "model",
            "e.unknown": "data",
        }

    def test_idempotent_per_run_and_path(self, tmp_path: Path):
        SessionLocal = _make_sync_session(tmp_path / "idem.db")
        run_id = _seed_run(SessionLocal)
        store = RunStateStore(SessionLocal)
        path = _write(tmp_path / "dup.png")

        assert store.register_artifacts(run_id, [path]) == 1
        assert store.register_artifacts(run_id, [path, path]) == 0
        with SessionLocal() as db:
            rows = db.scalars(select(Artifact).where(Artifact.run_id == run_id)).all()
            assert len(rows) == 1

    def test_missing_file_is_skipped_not_fatal(self, tmp_path: Path):
        SessionLocal = _make_sync_session(tmp_path / "miss.db")
        run_id = _seed_run(SessionLocal)
        store = RunStateStore(SessionLocal)
        good = _write(tmp_path / "good.png")
        ghost = str(tmp_path / "ghost.png")

        assert store.register_artifacts(run_id, [ghost, good]) == 1
        with SessionLocal() as db:
            rows = db.scalars(select(Artifact).where(Artifact.run_id == run_id)).all()
            assert [r.name for r in rows] == ["good.png"]

    def test_unknown_run_writes_nothing(self, tmp_path: Path):
        SessionLocal = _make_sync_session(tmp_path / "norun.db")
        store = RunStateStore(SessionLocal)
        path = _write(tmp_path / "x.png")
        assert store.register_artifacts("missing-run", [path]) == 0

    def test_empty_and_non_file_inputs(self, tmp_path: Path):
        SessionLocal = _make_sync_session(tmp_path / "edge.db")
        run_id = _seed_run(SessionLocal)
        store = RunStateStore(SessionLocal)
        assert store.register_artifacts(run_id, []) == 0
        assert store.register_artifacts(run_id, [str(tmp_path)]) == 0  # a directory


def test_finalize_registers_produced_files(tmp_path: Path, monkeypatch):
    """runner._finalize persists drained produced files alongside drift."""
    from autopipe.core.execution import ExecutionResult
    from autopipe.core.run_state import RunState

    SessionLocal = _make_sync_session(tmp_path / "fin.db")
    run_id = _seed_run(SessionLocal)
    monkeypatch.setattr(runner, "_SyncSessionLocal", SessionLocal)
    monkeypatch.setattr(runner, "_event_loop", None)
    store = RunStateStore(SessionLocal)
    store.mark_run_running(run_id)
    path = _write(tmp_path / "fin.png", b"fin-bytes")

    result = ExecutionResult(run_id=run_id, pipeline_name="p", state=RunState.SUCCESS)
    runner._finalize(run_id, result, store, produced=[path])

    with SessionLocal() as db:
        run = db.get(Run, run_id)
        assert run.status == RunStatus.SUCCESS
        row = db.scalars(select(Artifact).where(Artifact.run_id == run_id)).one()
        assert row.sha256 == hashlib.sha256(b"fin-bytes").hexdigest()


async def test_run_produces_and_registers_chart_artifact(
    auth_client: AsyncClient, seed_pipeline, db_session, wait_terminal, tmp_path, monkeypatch
):
    """E2E: a real dashboard run that writes a chart ends with a registered row."""
    import matplotlib

    matplotlib.use("Agg")
    monkeypatch.chdir(tmp_path)  # ChartGenerator writes ./figures relative to CWD

    resp = await auth_client.post(
        f"/api/v1/pipelines/{seed_pipeline.id}/runs",
        json={
            "config_override": {
                "name": "artifact-e2e",
                "steps": [{"name": "dl", "type": "sample_data_loader"}],
            }
        },
    )
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["id"]
    assert await wait_terminal(run_id) is RunStatus.SUCCESS

    db_session.expire_all()
    rows = (
        (await db_session.execute(select(Artifact).where(Artifact.run_id == run_id)))
        .scalars()
        .all()
    )
    assert rows, "DataLoaderStep.visualize must have produced a registered chart"
    for row in rows:
        assert row.sha256, "content address required at registration"
        assert row.file_size and row.file_size > 0
        assert os.path.isfile(row.file_path)
        figures = tmp_path / "figures"
        assert figures in Path(row.file_path).parents
