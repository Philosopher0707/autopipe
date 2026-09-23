"""M5/M6: run provenance (config_hash, env/code/seed snapshot) and run_number race."""

import json
import platform

from app.api.v1.endpoints import run_numbers
from app.core.provenance import build_provenance, seeds_from_config
from app.db.models import Run, RunStatus, hash_config
from httpx import AsyncClient

SENTINEL = "sk-sentinel-env-only-I12"


def test_provenance_never_captures_environment_secrets(monkeypatch):
    """I12-C: provenance is a fixed field list — an ambient key stays out."""
    monkeypatch.setenv("OPENROUTER_API_KEY", SENTINEL)
    prov = build_provenance("test", {"steps": [], "seed": 7})
    assert SENTINEL not in json.dumps(prov)
    assert prov["environment"]["packages"], "sanity: fingerprint still populated"


async def test_secret_env_never_lands_in_run_database(
    auth_client: AsyncClient, seed_pipeline, wait_terminal, tmp_path, monkeypatch
):
    """I12-C end-to-end: env key + full admit→run→finalize flow, DB file grep.

    One grep over the SQLite file (incl. WAL) covers Run.config, provenance,
    events, metrics, and logs together — the union of durable run state.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", SENTINEL)

    resp = await auth_client.post(f"/api/v1/pipelines/{seed_pipeline.id}/runs")
    assert resp.status_code == 201, resp.text
    assert await wait_terminal(resp.json()["id"])
    assert SENTINEL not in resp.text

    blobs = b"".join(p.read_bytes() for p in sorted(tmp_path.glob("test.db*")))
    assert SENTINEL.encode() not in blobs, "credential material must never reach the DB file"


def test_hash_config_is_deterministic_and_order_independent():
    a = hash_config({"b": 1, "a": {"y": 2, "x": 3}})
    b = hash_config({"a": {"x": 3, "y": 2}, "b": 1})
    assert a == b, "canonical JSON must make key order irrelevant"
    assert a is not None and len(a) == 64
    assert hash_config(None) is None
    assert hash_config({"a": 1}) != hash_config({"a": 2}), "different configs must differ"


async def test_pipeline_config_hash_written_on_create(auth_client: AsyncClient):
    """The writer-less Pipeline.config_hash column now tracks Pipeline.config."""
    config = {"steps": [{"name": "s", "type": "print"}]}
    resp = await auth_client.post("/api/v1/pipelines", json={"name": "hash-pipe", "config": config})
    assert resp.status_code == 201, resp.text
    assert resp.json()["config_hash"] == hash_config(config)


async def test_run_stores_config_hash_at_insert(
    auth_client: AsyncClient, seed_pipeline, db_session, wait_terminal
):
    """A triggered run persists the hash of the config it was created with."""
    expected = hash_config(seed_pipeline.config)  # capture before expire_all
    resp = await auth_client.post(f"/api/v1/pipelines/{seed_pipeline.id}/runs")
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["id"]
    assert await wait_terminal(run_id)
    db_session.expire_all()
    run = await db_session.get(Run, run_id)
    assert run is not None
    assert run.config_hash == hash_config(run.config)
    assert run.config_hash == expected


async def _occupy_run_number(db_session, pipeline_id: str, run_number: int) -> None:
    db_session.add(
        Run(pipeline_id=pipeline_id, status=RunStatus.PENDING, run_number=run_number, config={})
    )
    await db_session.commit()


async def test_duplicate_run_number_is_retried(
    auth_client: AsyncClient, seed_pipeline, db_session, monkeypatch
):
    """A stale max (concurrent insert) loses the race, retries, and succeeds."""
    await _occupy_run_number(db_session, seed_pipeline.id, 1)

    real_next = run_numbers._next_number
    calls = {"n": 0}

    async def stale_then_real(db, pipeline_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return 1  # first attempt reads a stale max and collides
        return await real_next(db, pipeline_id)

    monkeypatch.setattr(run_numbers, "_next_number", stale_then_real)

    resp = await auth_client.post(f"/api/v1/pipelines/{seed_pipeline.id}/runs")
    assert resp.status_code == 201, resp.text
    assert resp.json()["run_number"] == 2
    assert calls["n"] >= 2, "the helper must have retried after the conflict"


async def test_run_number_conflict_exhaustion_is_409(
    auth_client: AsyncClient, seed_pipeline, db_session, monkeypatch
):
    """When every attempt collides, the caller gets an explicit 409, not a 500."""
    await _occupy_run_number(db_session, seed_pipeline.id, 1)

    async def always_stale(db, pipeline_id):
        return 1

    monkeypatch.setattr(run_numbers, "_next_number", always_stale)

    resp = await auth_client.post(f"/api/v1/pipelines/{seed_pipeline.id}/runs")
    assert resp.status_code == 409, resp.text
    assert "run number" in resp.json()["detail"]


async def test_pipeline_config_hash_updates_on_config_change(
    auth_client: AsyncClient, seed_pipeline, db_session
):
    """The validates hook rewrites Pipeline.config_hash when config changes."""
    old_hash = (await auth_client.get(f"/api/v1/pipelines/{seed_pipeline.id}")).json()[
        "config_hash"
    ]
    new_config = {"steps": [{"name": "changed", "type": "print"}]}
    resp = await auth_client.put(
        f"/api/v1/pipelines/{seed_pipeline.id}", json={"config": new_config}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["config_hash"] == hash_config(new_config)
    assert resp.json()["config_hash"] != old_hash


# --- env/code/seed snapshot (PROVENANCE_MODEL steps 2-3) ---


def test_build_provenance_structure():
    prov = build_provenance("dashboard", {"seed": 42})
    assert prov["engine_version"], "engine_version must be recorded"
    assert prov["origin"] == "dashboard"
    assert prov["environment"]["python"] == platform.python_version()
    assert prov["environment"]["platform"]
    assert isinstance(prov["environment"]["packages"], dict)
    assert prov["code_revision"], "code_revision is a sha or 'unavailable', never empty"
    assert prov["seeds"] == {"seed": 42}


def test_build_provenance_code_revision_unavailable_when_git_fails(monkeypatch):
    """Git failure records the explicit marker, never a placeholder or crash."""

    def boom(*args, **kwargs):
        raise RuntimeError("no git")

    monkeypatch.setattr("app.core.provenance.subprocess.run", boom)
    prov = build_provenance("dashboard")
    assert prov["code_revision"] == "unavailable"


def test_seeds_from_config():
    assert seeds_from_config(None) is None
    assert seeds_from_config({}) is None
    assert seeds_from_config({"steps": []}) is None
    assert seeds_from_config({"seeds": [1, 2]}) == {"seeds": [1, 2]}
    assert seeds_from_config({"seed": 7, "steps": []}) == {"seed": 7}


async def test_triggered_run_persists_provenance_snapshot(
    auth_client: AsyncClient, seed_pipeline, db_session, wait_terminal
):
    """A real triggered run carries the env/code/origin snapshot through the API."""
    resp = await auth_client.post(f"/api/v1/pipelines/{seed_pipeline.id}/runs")
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["id"]
    assert await wait_terminal(run_id)

    detail = (await auth_client.get(f"/api/v1/runs/{run_id}")).json()
    prov = detail.get("provenance")
    assert prov, "triggered runs must persist a provenance snapshot"
    assert prov["origin"] == "dashboard"
    assert prov["engine_version"]
    assert prov["environment"]["python"] == platform.python_version()
    assert prov["code_revision"]
    assert "seeds" in prov

    db_session.expire_all()
    run = await db_session.get(Run, run_id)
    assert run is not None
    assert run.provenance == prov, "API response must equal the durable row"
