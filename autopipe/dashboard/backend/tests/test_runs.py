"""Tests for run endpoints."""

import pytest
from httpx import AsyncClient

from app.db.models import Pipeline, Run, RunStatus


pytestmark = pytest.mark.asyncio


async def _create_run(client: AsyncClient, pipeline_id: str) -> dict:
    """Helper to create a run via the pipeline trigger endpoint."""
    resp = await client.post(f"/api/v1/pipelines/{pipeline_id}/runs")
    assert resp.status_code == 201
    return resp.json()


async def test_list_runs_empty(client: AsyncClient):
    """GET /runs returns empty list when no runs exist."""
    resp = await client.get("/api/v1/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []


async def test_create_run_via_pipeline(client: AsyncClient, seed_pipeline: Pipeline):
    """Triggering a run via POST /pipelines/{id}/runs creates a run."""
    data = await _create_run(client, seed_pipeline.id)
    assert data["pipeline_id"] == seed_pipeline.id
    assert data["status"] in ("pending", "running")


async def test_get_run(client: AsyncClient, seed_pipeline: Pipeline):
    """GET /runs/{id} returns run details."""
    run_data = await _create_run(client, seed_pipeline.id)
    resp = await client.get(f"/api/v1/runs/{run_data['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == run_data["id"]


async def test_get_run_not_found(client: AsyncClient):
    """GET /runs/nonexistent returns 404."""
    resp = await client.get("/api/v1/runs/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_update_run_status(client: AsyncClient, seed_pipeline: Pipeline):
    """PATCH /runs/{id} updates run status."""
    run_data = await _create_run(client, seed_pipeline.id)
    resp = await client.patch(f"/api/v1/runs/{run_data['id']}", json={
        "status": "running",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] in ("running", "RUNNING")


async def test_cancel_run(client: AsyncClient, seed_pipeline: Pipeline):
    """PATCH /runs/{id} with status=cancelled cancels the run."""
    run_data = await _create_run(client, seed_pipeline.id)
    resp = await client.patch(f"/api/v1/runs/{run_data['id']}", json={
        "status": "cancelled",
    })
    assert resp.status_code == 200
    assert resp.json()["status"] in ("cancelled", "CANCELLED")


async def test_get_run_steps(client: AsyncClient, db_session, seed_pipeline: Pipeline):
    """GET /runs/{id}/steps returns step list."""
    run_data = await _create_run(client, seed_pipeline.id)
    resp = await client.get(f"/api/v1/runs/{run_data['id']}/steps")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


async def test_delete_run(client: AsyncClient, seed_pipeline: Pipeline):
    """DELETE /runs/{id} removes the run."""
    run_data = await _create_run(client, seed_pipeline.id)
    resp = await client.delete(f"/api/v1/runs/{run_data['id']}")
    assert resp.status_code == 204

    resp = await client.get(f"/api/v1/runs/{run_data['id']}")
    assert resp.status_code == 404