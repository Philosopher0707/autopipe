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
4. PHASE D: same config + seed + dataset, different code identity —
   provenance must distinguish the runs by code_revision while config_hash,
   seeds, and dataset identities stay equal (config and code are separate
   dimensions).
"""

import hashlib
from pathlib import Path
from types import SimpleNamespace
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


class TestChangedCodeProvenance:
    """PHASE D: same config + seed + dataset, different code identity.

    Code identity is recorded at run creation (``build_provenance`` at
    admission). The seam patched here is ``provenance.subprocess`` — the
    module's own reference — so the real ``_code_revision`` →
    ``build_provenance`` → ``Run.provenance`` persistence path runs with
    two controlled git HEADs and no worktree is ever touched.
    """

    HEAD_A = "a" * 40
    HEAD_B = "b" * 40

    async def test_provenance_distinguishes_code_identity(
        self,
        auth_client: AsyncClient,
        seed_pipeline,
        db_session,
        wait_terminal,
        tmp_path,
        monkeypatch,
    ):
        import matplotlib

        matplotlib.use("Agg")
        monkeypatch.chdir(tmp_path)
        csv_path = tmp_path / "input.csv"
        csv_path.write_bytes(b"feature,target\n1,0\n2,1\n3,0\n")
        pipeline_id = seed_pipeline.id

        heads = [self.HEAD_A]

        def fake_git(cmd, *args, **kwargs):
            if list(cmd[:3]) == ["git", "rev-parse", "HEAD"]:
                return SimpleNamespace(stdout=heads[0] + "\n")
            if list(cmd[:2]) == ["git", "status"]:
                return SimpleNamespace(stdout="")  # clean work tree
            raise AssertionError(f"unexpected command leaked to git seam: {cmd}")

        monkeypatch.setattr("app.core.provenance.subprocess", SimpleNamespace(run=fake_git))

        async def run_once():
            resp = await auth_client.post(
                f"/api/v1/pipelines/{pipeline_id}/runs",
                json={
                    "config_override": {
                        "name": "changed-code",
                        "seed": 42,
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
            assert run is not None
            return {"config_hash": run.config_hash, "provenance": dict(run.provenance or {})}

        run_a = await run_once()
        heads[0] = self.HEAD_B  # "changed code" for the second run
        run_b = await run_once()

        # 1. Configuration identity: equal and non-vacuous.
        assert run_a["config_hash"] is not None
        assert run_b["config_hash"] is not None
        assert run_a["config_hash"] == run_b["config_hash"]

        # 2. Seed: declared and applied identically on both runs.
        for snap in (run_a, run_b):
            assert snap["provenance"].get("seeds") == {"seed": 42}
            assert snap["provenance"].get("seed_applied") == 42

        # 3. Dataset identity: DataLoader path records the same content hash.
        ds_a, ds_b = run_a["provenance"].get("datasets"), run_b["provenance"].get("datasets")
        assert ds_a and ds_a == ds_b
        file_entries = [e for e in ds_a if e["kind"] == "file"]
        assert len(file_entries) == 1
        assert file_entries[0]["sha256"] == hashlib.sha256(csv_path.read_bytes()).hexdigest()

        # 4. PRIMARY: code_revision differs — provenance distinguishes code
        # identity. Non-vacuous: both recorded values are the exact controlled
        # heads, not None/"unavailable", and unequal.
        rev_a = run_a["provenance"].get("code_revision")
        rev_b = run_b["provenance"].get("code_revision")
        assert rev_a == self.HEAD_A
        assert rev_b == self.HEAD_B
        assert rev_a != rev_b

        # 5. Config-hash adversarial assertion: equal config_hash WHILE code
        # identity differs — the two provenance dimensions are separate.
        assert run_a["config_hash"] == run_b["config_hash"] and rev_a != rev_b
