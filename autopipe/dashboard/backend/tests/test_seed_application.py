"""Phase A: declared seed is admitted, applied at execution, recorded distinctly.

DECLARED = provenance.seeds written at Run creation from the config.
APPLIED  = provenance.seed_applied written at finalization iff the engine
           actually initialized run-local RNG from that seed.
"""

from app.core.provenance import build_provenance
from app.db.models import Run, RunStatus, hash_config
from httpx import AsyncClient


def _seeded_config(seed=None):
    config = {"name": "seeded", "steps": [{"name": "s", "type": "print"}]}
    if seed is not None:
        config["seed"] = seed
    return config


async def test_seed_is_admitted_and_applied_end_to_end(
    auth_client: AsyncClient, seed_pipeline, db_session, wait_terminal
):
    resp = await auth_client.post(
        f"/api/v1/pipelines/{seed_pipeline.id}/runs",
        json={"config_override": _seeded_config(seed=42)},
    )
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["id"]
    status = await wait_terminal(run_id)
    assert status is RunStatus.SUCCESS

    db_session.expire_all()
    run = await db_session.get(Run, run_id)
    assert run is not None
    prov = run.provenance or {}
    assert prov.get("seeds") == {"seed": 42}, "DECLARED"
    assert prov.get("seed_applied") == 42, "APPLIED"


async def test_unseeded_run_records_neither_declared_nor_applied(
    auth_client: AsyncClient, seed_pipeline, db_session, wait_terminal
):
    resp = await auth_client.post(
        f"/api/v1/pipelines/{seed_pipeline.id}/runs",
        json={"config_override": _seeded_config()},
    )
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["id"]
    assert await wait_terminal(run_id) is RunStatus.SUCCESS

    db_session.expire_all()
    run = await db_session.get(Run, run_id)
    assert run is not None
    prov = run.provenance or {}
    assert not prov.get("seeds")
    assert "seed_applied" not in prov


async def test_load_failure_declares_but_never_applies(
    auth_client: AsyncClient, seed_pipeline, db_session, wait_terminal, monkeypatch
):
    from app.executor import runner

    def boom(config):
        raise RuntimeError("synthetic load failure")

    monkeypatch.setattr(runner, "_load_pipeline", boom)
    resp = await auth_client.post(
        f"/api/v1/pipelines/{seed_pipeline.id}/runs",
        json={"config_override": _seeded_config(seed=42)},
    )
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["id"]
    assert await wait_terminal(run_id) is RunStatus.FAILED

    db_session.expire_all()
    run = await db_session.get(Run, run_id)
    assert run is not None
    prov = run.provenance or {}
    assert prov.get("seeds") == {"seed": 42}, "declared at creation regardless"
    assert "seed_applied" not in prov, "engine never ran, so nothing was applied"


async def test_negative_seed_is_rejected_at_admission(auth_client: AsyncClient, seed_pipeline):
    resp = await auth_client.post(
        f"/api/v1/pipelines/{seed_pipeline.id}/runs",
        json={"config_override": _seeded_config(seed=-1)},
    )
    assert resp.status_code == 400, resp.text


async def test_seed_is_part_of_config_identity(
    auth_client: AsyncClient, seed_pipeline, db_session, wait_terminal
):
    run_ids = []
    for seed in (1, 2):
        resp = await auth_client.post(
            f"/api/v1/pipelines/{seed_pipeline.id}/runs",
            json={"config_override": _seeded_config(seed=seed)},
        )
        assert resp.status_code == 201, resp.text
        run_ids.append(resp.json()["id"])
        assert await wait_terminal(run_ids[-1]) is RunStatus.SUCCESS

    db_session.expire_all()
    hashes = []
    for run_id in run_ids:
        run = await db_session.get(Run, run_id)
        assert run is not None
        assert run.config_hash == hash_config(run.config)
        hashes.append(run.config_hash)
    assert hashes[0] != hashes[1], "different seeds must be different configs"


def test_build_provenance_still_snapshots_declared_seed():
    prov = build_provenance("test", {"steps": [], "seed": 7})
    assert prov["seeds"] == {"seed": 7}
    assert "seed_applied" not in prov, "application is a runtime fact, not creation"
