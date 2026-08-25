"""Tests for chart data endpoints."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_run_metrics_over_time(client: AsyncClient):
    """GET /charts/run-metrics-over-time returns chart data."""
    resp = await client.get(
        "/api/v1/charts/run-metrics-over-time",
        params={
            "metric": "accuracy",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "metric" in data
    assert "points" in data


async def test_step_durations(client: AsyncClient):
    """GET /charts/step-durations returns step durations."""
    resp = await client.get(
        "/api/v1/charts/step-durations",
        params={
            "run_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "steps" in data


async def test_create_chart_artifact(client: AsyncClient):
    """POST /charts/artifacts creates a chart artifact."""
    resp = await client.post(
        "/api/v1/charts/artifacts",
        json={
            "chart_type": "line",
            "title": "Test Chart",
            "data": {"x": [1, 2, 3], "y": [4, 5, 6]},
        },
    )
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


async def test_training_metrics_trace(client: AsyncClient, seed_pipeline):
    """GET /charts/training-metrics-trace returns training curve data."""
    # Create a run via pipeline trigger
    run_resp = await client.post(f"/api/v1/pipelines/{seed_pipeline.id}/runs")
    assert run_resp.status_code == 201
    run_id = run_resp.json()["id"]

    # Log training metrics for the run
    for epoch in range(1, 4):
        for metric_name, value in [
            ("loss", 0.5 / epoch),
            ("val_loss", 0.55 / epoch),
            ("accuracy", 0.6 + 0.1 * epoch),
            ("val_accuracy", 0.58 + 0.09 * epoch),
        ]:
            log_resp = await client.post(
                "/api/v1/charts/metric-logs",
                json={
                    "run_id": run_id,
                    "metric_name": metric_name,
                    "step_index": epoch,
                    "value": round(value, 4),
                },
            )
            assert log_resp.status_code == 201

    resp = await client.get("/api/v1/charts/training-metrics-trace", params={"run_id": run_id})
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run_id
    assert "run_number" in data
    assert "points" in data
    assert isinstance(data["points"], list)
    assert len(data["points"]) == 3
    # Verify first epoch has expected keys
    first = data["points"][0]
    assert "epoch" in first
    assert "loss" in first
    assert "val_loss" in first
    assert "accuracy" in first
    assert "val_accuracy" in first


async def test_training_metrics_trace_prefixed(client: AsyncClient, seed_pipeline):
    """GET /charts/training-metrics-trace normalizes train/* metric names."""
    run_resp = await client.post(f"/api/v1/pipelines/{seed_pipeline.id}/runs")
    assert run_resp.status_code == 201
    run_id = run_resp.json()["id"]

    # Log metrics with train/ prefixed names
    for epoch in range(1, 4):
        for metric_name, value in [
            ("train/epoch_loss", 0.5 / epoch),
            ("val_loss", 0.55 / epoch),
            ("train/epoch_accuracy", 0.6 + 0.1 * epoch),
            ("val_accuracy", 0.58 + 0.09 * epoch),
        ]:
            log_resp = await client.post(
                "/api/v1/charts/metric-logs",
                json={
                    "run_id": run_id,
                    "metric_name": metric_name,
                    "step_index": epoch,
                    "value": round(value, 4),
                },
            )
            assert log_resp.status_code == 201

    resp = await client.get("/api/v1/charts/training-metrics-trace", params={"run_id": run_id})
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run_id
    assert len(data["points"]) == 3
    first = data["points"][0]
    assert first["loss"] is not None
    assert first["val_loss"] is not None
    assert first["accuracy"] is not None
    assert first["val_accuracy"] is not None


async def test_training_metrics_trace_404(client: AsyncClient):
    """GET /charts/training-metrics-trace returns 404 for unknown run."""
    resp = await client.get(
        "/api/v1/charts/training-metrics-trace",
        params={
            "run_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert resp.status_code == 404
