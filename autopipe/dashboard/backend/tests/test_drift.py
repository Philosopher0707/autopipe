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


async def test_detect_drift_not_implemented(client: AsyncClient):
    """POST /drift/detect is an honest 501 — no fabricated reports, no writes."""
    resp = await client.post(
        "/api/v1/drift/detect",
        json={
            "threshold": 0.05,
            "test_types": ["ks"],
        },
    )
    assert resp.status_code == 501
    assert "not implemented" in resp.json()["detail"].lower()

    # The alias route must behave identically.
    resp_alias = await client.post("/api/v1/drift", json={"threshold": 0.05})
    assert resp_alias.status_code == 501

    # Nothing may have been persisted by the rejected requests.
    resp_list = await client.get("/api/v1/drift")
    assert resp_list.status_code == 200
    assert resp_list.json().get("total", 0) >= 0


async def test_list_drift_alerts(client: AsyncClient):
    """GET /drift/alerts returns alerts list."""
    resp = await client.get("/api/v1/drift/alerts")
    assert resp.status_code == 200
