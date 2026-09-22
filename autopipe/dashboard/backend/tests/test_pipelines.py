"""Tests for pipeline endpoints."""

import pytest
from app.db.models import Pipeline, RunStatus
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_list_pipelines_empty(auth_client: AsyncClient):
    """GET /pipelines returns empty list when no pipelines exist."""
    resp = await auth_client.get("/api/v1/pipelines")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_create_pipeline(auth_client: AsyncClient):
    """POST /pipelines creates a pipeline."""
    resp = await auth_client.post(
        "/api/v1/pipelines",
        json={
            "name": "my-pipeline",
            "description": "A test pipeline",
            "config": {"steps": [{"name": "step1", "type": "print"}]},
            "tags": ["test"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "my-pipeline"
    assert data["id"] is not None
    assert data["run_count"] == 0


async def test_get_pipeline(auth_client: AsyncClient, seed_pipeline: Pipeline):
    """GET /pipelines/{id} returns the pipeline."""
    resp = await auth_client.get(f"/api/v1/pipelines/{seed_pipeline.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "test-pipeline"
    assert data["id"] == seed_pipeline.id


async def test_get_pipeline_not_found(auth_client: AsyncClient):
    """GET /pipelines/nonexistent returns 404."""
    resp = await auth_client.get("/api/v1/pipelines/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_update_pipeline(auth_client: AsyncClient, seed_pipeline: Pipeline):
    """PUT /pipelines/{id} updates the pipeline."""
    resp = await auth_client.put(
        f"/api/v1/pipelines/{seed_pipeline.id}",
        json={
            "description": "Updated description",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["description"] == "Updated description"


async def test_delete_pipeline(auth_client: AsyncClient, seed_pipeline: Pipeline):
    """DELETE /pipelines/{id} removes the pipeline."""
    resp = await auth_client.delete(f"/api/v1/pipelines/{seed_pipeline.id}")
    assert resp.status_code == 204

    # Verify it's gone
    resp = await auth_client.get(f"/api/v1/pipelines/{seed_pipeline.id}")
    assert resp.status_code == 404


async def test_delete_pipeline_not_found(auth_client: AsyncClient):
    """DELETE /pipelines/nonexistent returns 404."""
    resp = await auth_client.delete("/api/v1/pipelines/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_list_pipelines_with_search(auth_client: AsyncClient, seed_pipeline: Pipeline):
    """GET /pipelines?search= filters by name."""
    # Create another pipeline with different name
    await auth_client.post("/api/v1/pipelines", json={"name": "other-pipeline"})

    resp = await auth_client.get("/api/v1/pipelines", params={"search": "test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    names = [p["name"] for p in data["items"]]
    assert "test-pipeline" in names


async def test_trigger_run(auth_client: AsyncClient, seed_pipeline: Pipeline, wait_terminal):
    """POST /pipelines/{id}/runs creates a run and executes it to SUCCESS.

    The response is written before dispatch, so its status is still pending;
    the real claim is that the shared-database worker drives it terminal.
    """
    resp = await auth_client.post(f"/api/v1/pipelines/{seed_pipeline.id}/runs")
    assert resp.status_code == 201
    data = resp.json()
    assert data["pipeline_id"] == seed_pipeline.id
    assert data["status"] in ("pending", "running")
    assert await wait_terminal(data["id"]) is RunStatus.SUCCESS
