"""Tests for chart data endpoints."""

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


async def test_run_metrics_over_time(client: AsyncClient):
    """GET /charts/run-metrics-over-time returns chart data."""
    resp = await client.get("/api/v1/charts/run-metrics-over-time", params={
        "metric": "accuracy",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "metric" in data
    assert "points" in data


async def test_step_durations(client: AsyncClient):
    """GET /charts/step-durations returns step durations."""
    resp = await client.get("/api/v1/charts/step-durations", params={
        "run_id": "00000000-0000-0000-0000-000000000000",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "steps" in data


async def test_create_chart_artifact(client: AsyncClient):
    """POST /charts/artifacts creates a chart artifact."""
    resp = await client.post("/api/v1/charts/artifacts", json={
        "chart_type": "line",
        "title": "Test Chart",
        "data": {"x": [1, 2, 3], "y": [4, 5, 6]},
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Test Chart"
    assert data["chart_type"] == "line"


async def test_list_chart_artifacts(client: AsyncClient):
    """GET /charts/artifacts returns chart artifacts list."""
    resp = await client.get("/api/v1/charts/artifacts")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data