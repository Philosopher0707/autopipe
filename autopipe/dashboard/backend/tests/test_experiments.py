"""Tests for experiment endpoints."""

import pytest
from app.db.models import Experiment, Pipeline
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_create_experiment(auth_client: AsyncClient):
    """POST /experiments creates a new experiment."""
    resp = await auth_client.post(
        "/api/v1/experiments",
        json={
            "name": "my-experiment",
            "description": "Testing hyperparameter tuning",
            "config": {"search_space": {"lr": {"type": "float", "low": 0.001, "high": 0.1}}},
            "tags": ["ml", "test"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "my-experiment"
    assert data["status"] == "pending"
    assert data["run_count"] == 0


async def test_list_experiments(auth_client: AsyncClient):
    """GET /experiments returns paginated list."""
    # Create an experiment first
    await auth_client.post("/api/v1/experiments", json={"name": "exp-1"})
    resp = await auth_client.get("/api/v1/experiments")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


async def test_get_experiment(auth_client: AsyncClient, seed_experiment: Experiment):
    """GET /experiments/{id} returns experiment details."""
    resp = await auth_client.get(f"/api/v1/experiments/{seed_experiment.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "test-experiment"


async def test_get_experiment_not_found(auth_client: AsyncClient):
    """GET /experiments/nonexistent returns 404."""
    resp = await auth_client.get("/api/v1/experiments/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_update_experiment(auth_client: AsyncClient, seed_experiment: Experiment):
    """PATCH /experiments/{id} updates the experiment."""
    resp = await auth_client.patch(
        f"/api/v1/experiments/{seed_experiment.id}",
        json={
            "description": "Updated description",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "Updated description"


async def test_delete_experiment(auth_client: AsyncClient, seed_experiment: Experiment):
    """DELETE /experiments/{id} removes the experiment."""
    resp = await auth_client.delete(f"/api/v1/experiments/{seed_experiment.id}")
    assert resp.status_code == 204


async def test_launch_trials_simulate_rejected(
    auth_client: AsyncClient, seed_experiment: Experiment, seed_pipeline: Pipeline
):
    """POST /experiments/{id}/trials with simulate=true is an honest 501."""
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
    assert "no longer supported" in resp.json()["detail"].lower()


async def test_launch_trials_real_dispatch(
    auth_client: AsyncClient, seed_experiment: Experiment, seed_pipeline: Pipeline
):
    """POST /experiments/{id}/trials (default simulate=false) creates PENDING runs."""
    resp = await auth_client.post(
        f"/api/v1/experiments/{seed_experiment.id}/trials",
        json={
            "pipeline_id": seed_pipeline.id,
            "strategy": "random",
            "n_trials": 3,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["experiment_id"] == seed_experiment.id
    assert len(data["runs"]) == 3
