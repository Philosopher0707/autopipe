"""Phase C: dataset input identity lands in Run.provenance at finalization."""

import hashlib
from pathlib import Path
from uuid import uuid4

from app.db.models import Base, Pipeline, Run, RunStatus
from app.executor import runner
from app.executor.sink import RunStateStore
from httpx import AsyncClient
from sqlalchemy import create_engine
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


def test_record_dataset_inputs_merges_provenance(tmp_path: Path):
    SessionLocal = _make_sync_session(tmp_path / "ds.db")
    run_id = _seed_run(SessionLocal)
    store = RunStateStore(SessionLocal)

    with SessionLocal() as db:
        run = db.get(Run, run_id)
        run.provenance = {"seed_applied": 7, "origin": "dashboard"}
        db.commit()

    entries = [{"kind": "file", "source": "/tmp/x.csv", "format": "csv", "sha256": "ab" * 32}]
    store.record_dataset_inputs(run_id, entries)

    with SessionLocal() as db:
        prov = db.get(Run, run_id).provenance
        assert prov["datasets"] == entries
        assert prov["seed_applied"] == 7, "sibling provenance keys must survive"
        assert prov["origin"] == "dashboard"


def test_record_dataset_inputs_skips_bad_entries(tmp_path: Path):
    SessionLocal = _make_sync_session(tmp_path / "ds2.db")
    run_id = _seed_run(SessionLocal)
    store = RunStateStore(SessionLocal)

    store.record_dataset_inputs(
        run_id,
        [
            {"kind": "builtin", "name": "iris", "sha256": "unavailable"},
            "not-a-dict",
            {"kind": "file"},  # no source/name — kept? design: keep dicts only
        ],
    )
    with SessionLocal() as db:
        prov = db.get(Run, run_id).provenance
        datasets = prov["datasets"]
        assert all(isinstance(d, dict) for d in datasets)
        assert datasets[0]["name"] == "iris"


def test_record_dataset_inputs_unknown_run_noop(tmp_path: Path, caplog):
    SessionLocal = _make_sync_session(tmp_path / "ds3.db")
    store = RunStateStore(SessionLocal)
    store.record_dataset_inputs("missing-run", [{"kind": "builtin", "name": "x"}])
    # nothing to assert beyond "no raise"; absence of rows is implicit


def test_sha256_file_reexports_core_definition():
    from app.db.models import sha256_file as backend_sha256_file

    from autopipe.core.artifacts import sha256_file as core_sha256_file

    assert backend_sha256_file is core_sha256_file


def test_finalize_bridges_dataset_inputs(tmp_path: Path, monkeypatch):
    from autopipe.core.execution import ExecutionResult
    from autopipe.core.run_state import RunState

    SessionLocal = _make_sync_session(tmp_path / "ds-fin.db")
    run_id = _seed_run(SessionLocal)
    monkeypatch.setattr(runner, "_SyncSessionLocal", SessionLocal)
    monkeypatch.setattr(runner, "_event_loop", None)
    store = RunStateStore(SessionLocal)
    store.mark_run_running(run_id)

    result = ExecutionResult(run_id=run_id, pipeline_name="p", state=RunState.SUCCESS)
    entry = {"kind": "builtin", "name": "iris", "sha256": "unavailable"}
    runner._finalize(run_id, result, store, datasets=[entry])

    with SessionLocal() as db:
        run = db.get(Run, run_id)
        assert run.status == RunStatus.SUCCESS
        assert run.provenance["datasets"] == [entry]


async def test_e2e_file_loader_run_records_dataset_hash(
    auth_client: AsyncClient, seed_pipeline, db_session, wait_terminal, tmp_path, monkeypatch
):
    """A real dashboard run loading a CSV records content identity."""
    import matplotlib

    matplotlib.use("Agg")
    monkeypatch.chdir(tmp_path)

    blob = b"feature,target\n1,0\n2,1\n3,0\n"
    csv_path = tmp_path / "input.csv"
    csv_path.write_bytes(blob)

    resp = await auth_client.post(
        f"/api/v1/pipelines/{seed_pipeline.id}/runs",
        json={
            "config_override": {
                "name": "dataset-e2e",
                "steps": [
                    {
                        "name": "load",
                        "type": "data_loader",
                        "params": {"source": str(csv_path), "format": "csv"},
                    }
                ],
            }
        },
    )
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["id"]
    assert await wait_terminal(run_id) is RunStatus.SUCCESS

    db_session.expire_all()
    run = await db_session.get(Run, run_id)
    datasets = (run.provenance or {}).get("datasets")
    assert datasets, "dataset identity must be recorded on the run"
    assert datasets[0]["sha256"] == hashlib.sha256(blob).hexdigest()
    assert datasets[0]["source"] == str(csv_path.resolve())


async def test_e2e_builtin_loader_records_name(
    auth_client: AsyncClient, seed_pipeline, db_session, wait_terminal, tmp_path, monkeypatch
):
    import matplotlib

    matplotlib.use("Agg")
    monkeypatch.chdir(tmp_path)

    resp = await auth_client.post(
        f"/api/v1/pipelines/{seed_pipeline.id}/runs",
        json={
            "config_override": {
                "name": "builtin-e2e",
                "steps": [{"name": "dl", "type": "sample_data_loader"}],
            }
        },
    )
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["id"]
    assert await wait_terminal(run_id) is RunStatus.SUCCESS

    db_session.expire_all()
    run = await db_session.get(Run, run_id)
    datasets = (run.provenance or {}).get("datasets")
    assert datasets == [{"kind": "builtin", "name": "iris", "sha256": "unavailable"}]
    # sklearn version pins builtin content — recorded in environment
    packages = (run.provenance or {}).get("environment", {}).get("packages", {})
    assert "scikit-learn" in packages
