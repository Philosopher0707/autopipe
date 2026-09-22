"""Run admission: no Run is created for a configuration that cannot run.

Invariants I11/I12/I19. Before admission existed, two endpoints decided
"is this runnable?" differently and both could persist a Run they would never
execute:

* ``POST /pipelines/{id}/runs`` created the Run unconditionally, then dispatched
  only when the config happened to contain a ``"steps"`` key.
* ``POST /experiments/{id}/trials`` created and committed its runs, and only then
  returned 501 for ``simulate=true`` — leaving orphaned PENDING runs behind.

These tests pin the corrected behavior: a rejection persists nothing.
"""

import uuid

import pytest
from app.db.models import Pipeline, Run
from app.executor.admission import RunAdmissionError, admit_run_config
from httpx import AsyncClient
from sqlalchemy import func, select

# A config that passes schema validation and whose step class is importable, but
# which cannot be constructed: `data_loader` takes `source`, not `dataset`.
UNBUILDABLE = {
    "name": "unbuildable",
    "steps": [{"name": "load", "type": "data_loader", "params": {"dataset": "iris"}}],
}
LOADABLE = {
    "name": "loadable",
    "steps": [{"name": "step1", "type": "print", "params": {"message": "hi"}}],
}


class TestAdmitRunConfig:
    """Unit contract of the admission gate."""

    def test_accepts_a_loadable_config(self):
        assert admit_run_config(LOADABLE) == LOADABLE

    def test_returns_a_copy_not_the_caller_object(self):
        admitted = admit_run_config(LOADABLE)
        assert admitted is not LOADABLE, "callers must not be able to mutate the stored config"

    def test_rejects_missing_config(self):
        with pytest.raises(RunAdmissionError, match="no pipeline configuration"):
            admit_run_config(None)

    def test_rejects_non_mapping(self):
        with pytest.raises(RunAdmissionError, match="must be an object"):
            admit_run_config(["not", "a", "mapping"])

    def test_rejects_unbuildable_config(self):
        with pytest.raises(RunAdmissionError, match="dataset"):
            admit_run_config(UNBUILDABLE)

    def test_rejects_a_step_type_outside_the_allowlist(self):
        # The allowlist is the security boundary; admission must not weaken it.
        with pytest.raises(RunAdmissionError):
            admit_run_config({"name": "evil", "steps": [{"name": "x", "type": "os.system"}]})

    def test_every_seed_config_is_admissible(self):
        """Demo seeds must be runnable configs, not inert metadata."""
        from app.seed import PIPELINE_SEEDS

        assert PIPELINE_SEEDS, "seed list must not be empty"
        for seed in PIPELINE_SEEDS:
            admitted = admit_run_config(seed["config"])
            assert admitted["name"] == seed["name"]

    def test_rejects_a_cyclic_dependency_graph(self):
        cyclic = {
            "name": "cyclic",
            "steps": [
                {"name": "a", "type": "print", "depends_on": ["b"]},
                {"name": "b", "type": "print", "depends_on": ["a"]},
            ],
        }
        with pytest.raises(RunAdmissionError):
            admit_run_config(cyclic)


async def _run_count(db_session) -> int:
    """Total persisted runs, used to prove a rejection persisted nothing."""
    total = await db_session.scalar(select(func.count()).select_from(Run))
    return int(total or 0)


class TestTriggerRunAdmission:
    """POST /pipelines/{id}/runs must not persist a run it cannot execute."""

    async def test_unbuildable_override_is_rejected_and_persists_no_run(
        self, auth_client: AsyncClient, seed_pipeline: Pipeline, db_session
    ):
        before = await _run_count(db_session)

        resp = await auth_client.post(
            f"/api/v1/pipelines/{seed_pipeline.id}/runs",
            json={"config_override": UNBUILDABLE},
        )

        assert resp.status_code == 400, resp.text
        assert "Cannot run this configuration" in resp.json()["detail"]
        assert await _run_count(db_session) == before, "a rejected config must not create a Run"

    async def test_loadable_override_is_admitted_and_stored_verbatim(
        self, auth_client: AsyncClient, seed_pipeline: Pipeline, db_session
    ):
        resp = await auth_client.post(
            f"/api/v1/pipelines/{seed_pipeline.id}/runs",
            json={"config_override": LOADABLE},
        )

        assert resp.status_code == 201, resp.text
        run_id = resp.json()["id"]
        db_session.expire_all()
        run = await db_session.get(Run, run_id)
        assert run is not None
        assert run.config == LOADABLE

    async def test_pipeline_without_config_is_rejected(self, auth_client: AsyncClient, db_session):
        """A pipeline with no config cannot become an executable run."""
        bare = Pipeline(id=str(uuid.uuid4()), name="no-config-pipeline", config=None)
        db_session.add(bare)
        await db_session.commit()
        before = await _run_count(db_session)

        resp = await auth_client.post(f"/api/v1/pipelines/{bare.id}/runs")

        assert resp.status_code == 400, resp.text
        assert await _run_count(db_session) == before


class TestTrialAdmission:
    """POST /experiments/{id}/trials must not persist runs on a rejection."""

    async def test_simulate_rejection_persists_no_runs(
        self, auth_client: AsyncClient, seed_experiment, seed_pipeline: Pipeline, db_session
    ):
        """Regression: the 501 used to be raised *after* committing the runs."""
        before = await _run_count(db_session)

        resp = await auth_client.post(
            f"/api/v1/experiments/{seed_experiment.id}/trials",
            json={
                "pipeline_id": seed_pipeline.id,
                "strategy": "random",
                "n_trials": 3,
                "simulate": True,
            },
        )

        assert resp.status_code == 501
        assert await _run_count(db_session) == before, (
            "a rejected request must not leave orphaned PENDING runs behind"
        )

    async def test_unrunnable_pipeline_is_rejected_and_persists_no_runs(
        self, auth_client: AsyncClient, seed_experiment, db_session
    ):
        bad = Pipeline(id=str(uuid.uuid4()), name="unrunnable", config=UNBUILDABLE)
        db_session.add(bad)
        await db_session.commit()
        before = await _run_count(db_session)

        resp = await auth_client.post(
            f"/api/v1/experiments/{seed_experiment.id}/trials",
            json={"pipeline_id": bad.id, "strategy": "random", "n_trials": 2},
        )

        assert resp.status_code == 400, resp.text
        assert await _run_count(db_session) == before

    async def test_admitted_trials_create_the_requested_number_of_runs(
        self, auth_client: AsyncClient, seed_experiment, seed_pipeline: Pipeline, db_session
    ):
        resp = await auth_client.post(
            f"/api/v1/experiments/{seed_experiment.id}/trials",
            json={"pipeline_id": seed_pipeline.id, "strategy": "random", "n_trials": 3},
        )

        assert resp.status_code == 200, resp.text
        assert len(resp.json()["runs"]) == 3
