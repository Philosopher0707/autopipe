"""Tests for model registry endpoints."""

import pytest
from app.db.models import Model
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_create_model(auth_client: AsyncClient):
    """POST /models creates a new model."""
    resp = await auth_client.post(
        "/api/v1/models",
        json={
            "name": "my-classifier",
            "description": "A test classifier",
            "framework": "sklearn",
            "task_type": "classification",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "my-classifier"
    assert data["framework"] == "sklearn"


async def test_list_models(auth_client: AsyncClient):
    """GET /models returns paginated list."""
    resp = await auth_client.get("/api/v1/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


async def test_get_model(auth_client: AsyncClient, seed_model: Model):
    """GET /models/{id} returns model details."""
    resp = await auth_client.get(f"/api/v1/models/{seed_model.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "test-model"


async def test_get_model_not_found(auth_client: AsyncClient):
    """GET /models/nonexistent returns 404."""
    resp = await auth_client.get("/api/v1/models/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_update_model(auth_client: AsyncClient, seed_model: Model):
    """PATCH /models/{id} updates the model."""
    resp = await auth_client.patch(
        f"/api/v1/models/{seed_model.id}",
        json={
            "description": "Updated model description",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["description"] == "Updated model description"


async def test_delete_model(auth_client: AsyncClient, seed_model: Model):
    """DELETE /models/{id} removes the model."""
    resp = await auth_client.delete(f"/api/v1/models/{seed_model.id}")
    assert resp.status_code == 204
