"""Tests for drift detection endpoints."""

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


async def test_list_drift_reports(client: AsyncClient):
    """GET /drift returns drift reports list."""
    resp = await client.get("/api/v1/drift")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data or "total" in data or isinstance(data, list)


async def test_detect_drift(client: AsyncClient):
    """POST /drift/detect creates a drift report."""
    resp = await client.post("/api/v1/drift/detect", json={
        "threshold": 0.05,
        "test_types": ["ks"],
    })
    assert resp.status_code in (200, 201)


async def test_list_drift_alerts(client: AsyncClient):
    """GET /drift/alerts returns alerts list."""
    resp = await client.get("/api/v1/drift/alerts")
    assert resp.status_code == 200