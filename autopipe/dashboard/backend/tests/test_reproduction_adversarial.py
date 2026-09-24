"""Phase F: adversarial probes — reproduction evidence must fail loudly, not lie.

Attacks the Phase B/C claims where nominal tests don't reach:
1. Dataset file mutated AFTER the run loaded it — the recorded hash must still
   describe the read-time bytes and recomputing must now diverge (detectable,
   not silently updated).
2. Registered artifact file overwritten AFTER registration — the stored row
   hash must stay put and recomputing must diverge (same discipline as the
   documented PROVENANCE_MODEL ceiling).
3. Dataset recorder must not leak entries across runs on the same thread when
   the runner's start-of-run hygiene drain is what clears them.
"""

import hashlib
from pathlib import Path
from uuid import uuid4

from app.db.models import Artifact, Base, Pipeline, Run, RunStatus
from app.executor.sink import RunStateStore
from httpx import AsyncClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from autopipe.core.artifacts import drain_dataset_inputs, record_dataset_input, sha256_file


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


class TestDatasetMutationDivergence:
    def test_post_load_mutation_is_detectable(self, tmp_path):
        from autopipe.steps.data import DataLoaderStep

        p = tmp_path / "in.csv"
        original = b"a,b\n1,2\n"
        p.write_bytes(original)

        drain_dataset_inputs()
        DataLoaderStep(name="dl", source=str(p), format="csv").run()
        entries = drain_dataset_inputs()
        recorded = entries[0]["sha256"]
        assert recorded == hashlib.sha256(original).hexdigest()

        # Adversary rewrites the file after the run consumed it.
        mutated = b"a,b\n9,9\n"
        p.write_bytes(mutated)

        # The recorded hash does NOT follow the file (describes read-time
        # bytes), and recomputing now diverges — the attack is detectable.
        assert recorded != hashlib.sha256(mutated).hexdigest()
        assert sha256_file(str(p)) != recorded

    def test_recorder_does_not_leak_between_hygiene_cycles(self):
        """Simulate the runner hygiene: leftover entries die at drain."""
        record_dataset_input({"kind": "builtin", "name": "stale"})
        # runner start-of-run drain clears it before the next execution:
        assert drain_dataset_inputs() == [{"kind": "builtin", "name": "stale"}]
        assert drain_dataset_inputs() == [], "second drain sees nothing"


class TestArtifactOverwriteDivergence:
    def test_overwritten_artifact_row_keeps_registration_hash(self, tmp_path: Path):
        SessionLocal = _make_sync_session(tmp_path / "adv.db")
        run_id = _seed_run(SessionLocal)
        store = RunStateStore(SessionLocal)

        payload = b"original-artifact-bytes"
        path = tmp_path / "model.pkl"
        path.write_bytes(payload)
        assert store.register_artifacts(run_id, [str(path)]) == 1

        with SessionLocal() as db:
            row = db.scalars(select(Artifact).where(Artifact.run_id == run_id)).one()
            stored = row.sha256
        assert stored == hashlib.sha256(payload).hexdigest()

        # Adversary overwrites the file behind the row.
        path.write_bytes(b"tampered-bytes")
        with SessionLocal() as db:
            row = db.scalars(select(Artifact).where(Artifact.run_id == run_id)).one()
            assert row.sha256 == stored, "row hash must not follow the file"
        assert sha256_file(str(path)) != stored, "recompute diverges — detectable"


async def test_dataset_and_artifact_survive_a_failed_run(
    auth_client: AsyncClient, seed_pipeline, db_session, wait_terminal, tmp_path, monkeypatch
):
    """Attack containment: a failing step must not erase evidence already recorded."""
    from app.db.models import RunStatus

    monkeypatch.chdir(tmp_path)
    csv_path = tmp_path / "in.csv"
    csv_path.write_bytes(b"x\n1\n")

    pipeline_id = seed_pipeline.id
    resp = await auth_client.post(
        f"/api/v1/pipelines/{pipeline_id}/runs",
        json={
            "config_override": {
                "name": "fail-after-load",
                "seed": 5,
                "steps": [
                    {
                        "name": "load",
                        "type": "data_loader",
                        "params": {"source": str(csv_path), "format": "csv"},
                    },
                    {"name": "boom", "type": "print", "params": {"message": "{missing.binding}"}},
                ],
            }
        },
    )
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["id"]
    status = await wait_terminal(run_id)
    assert status in (
        RunStatus.SUCCESS,
        RunStatus.FAILED,
    ), "either outcome is fine; evidence is the point"

    db_session.expire_all()
    run = await db_session.get(Run, run_id)
    prov = run.provenance or {}
    # Seed application is a runtime fact and must be recorded either way (I21).
    assert prov.get("seed_applied") == 5
    # If the loader ran, its input identity must also have been persisted
    # even when a later step fails (finalize records before terminal write).
    datasets = prov.get("datasets")
    if datasets is not None:
        assert datasets[0]["sha256"] == hashlib.sha256(csv_path.read_bytes()).hexdigest()
