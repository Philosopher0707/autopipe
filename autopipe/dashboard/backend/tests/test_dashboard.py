"""Tests for dashboard overview endpoints."""

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


async def test_dashboard_overview(client: AsyncClient):
    """GET /dashboard/overview returns stats."""
    resp = await client.get("/api/v1/dashboard/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert "pipelines" in data
    assert "models" in data
    assert "experiments" in data


async def test_sidebar_counts(client: AsyncClient):
    """GET /dashboard/counts returns sidebar badge counts."""
    resp = await client.get("/api/v1/dashboard/counts")
    assert resp.status_code == 200
    data = resp.json()
    assert "pipelines_total" in data
    assert "pipelines_active" in data
    assert "experiments_total" in data
    assert "models_total" in data


async def test_health_check(client: AsyncClient):
    """GET /dashboard/health returns system health."""
    resp = await client.get("/api/v1/dashboard/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "services" in data


async def test_activity_feed(client: AsyncClient):
    """GET /dashboard/activity returns activity list."""
    resp = await client.get("/api/v1/dashboard/activity")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data