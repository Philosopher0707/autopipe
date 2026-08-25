"""Tests for run endpoints."""

import pytest
from app.db.models import Pipeline
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def _create_run(auth_client: AsyncClient, pipeline_id: str) -> dict:
    """Helper to create a run via the pipeline trigger endpoint."""
    resp = await auth_client.post(f"/api/v1/pipelines/{pipeline_id}/runs")
    assert resp.status_code == 201
    return resp.json()


async def test_list_runs_empty(auth_client: AsyncClient):
    """GET /runs returns empty list when no runs exist."""
    resp = await auth_client.get("/api/v1/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []


async def test_create_run_via_pipeline(auth_client: AsyncClient, seed_pipeline: Pipeline):
    """Triggering a run via POST /pipelines/{id}/runs creates a run."""
    data = await _create_run(auth_client, seed_pipeline.id)
    assert data["pipeline_id"] == seed_pipeline.id
    assert data["status"] in ("pending", "running")


async def test_get_run(auth_client: AsyncClient, seed_pipeline: Pipeline):
    """GET /runs/{id} returns run details."""
    run_data = await _create_run(auth_client, seed_pipeline.id)
    resp = await auth_client.get(f"/api/v1/runs/{run_data['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == run_data["id"]


async def test_get_run_not_found(auth_client: AsyncClient):
    """GET /runs/nonexistent returns 404."""
    resp = await auth_client.get("/api/v1/runs/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_update_run_status(auth_client: AsyncClient, seed_pipeline: Pipeline):
    """PATCH /runs/{id} updates run status."""
    run_data = await _create_run(auth_client, seed_pipeline.id)
    resp = await auth_client.patch(
        f"/api/v1/runs/{run_data['id']}",
        json={
            "status": "running",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] in ("running", "RUNNING")


async def test_cancel_run(auth_client: AsyncClient, seed_pipeline: Pipeline):
    """PATCH /runs/{id} with status=cancelled cancels the run."""
    run_data = await _create_run(auth_client, seed_pipeline.id)
    resp = await auth_client.patch(
        f"/api/v1/runs/{run_data['id']}",
        json={
            "status": "cancelled",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] in ("cancelled", "CANCELLED")


async def test_get_run_steps(auth_client: AsyncClient, db_session, seed_pipeline: Pipeline):
    """GET /runs/{id}/steps returns step list."""
    run_data = await _create_run(auth_client, seed_pipeline.id)
    resp = await auth_client.get(f"/api/v1/runs/{run_data['id']}/steps")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data


async def test_delete_run(auth_client: AsyncClient, seed_pipeline: Pipeline):
    """DELETE /runs/{id} removes the run."""
    run_data = await _create_run(auth_client, seed_pipeline.id)
    resp = await auth_client.delete(f"/api/v1/runs/{run_data['id']}")
    assert resp.status_code == 204

    resp = await auth_client.get(f"/api/v1/runs/{run_data['id']}")
    assert resp.status_code == 404


async def test_compare_runs(auth_client: AsyncClient, seed_pipeline: Pipeline):
    """POST /runs/compare returns structured comparison for multiple runs."""
    # Create two runs via the pipeline trigger endpoint
    run_a = await _create_run(auth_client, seed_pipeline.id)
    run_b = await _create_run(auth_client, seed_pipeline.id)
    run_id_a = run_a["id"]
    run_id_b = run_b["id"]

    # Patch runs with distinct configs and metrics for comparison
    await auth_client.patch(
        f"/api/v1/runs/{run_id_a}",
        json={
            "config": {"lr": 0.001, "epochs": 10, "batch_size": 32},
            "metrics": {"accuracy": 0.85, "loss": 0.25},
        },
    )
    await auth_client.patch(
        f"/api/v1/runs/{run_id_b}",
        json={
            "config": {"lr": 0.01, "epochs": 10, "batch_size": 64},
            "metrics": {"accuracy": 0.88, "loss": 0.20},
        },
    )

    resp = await auth_client.post("/api/v1/runs/compare", json={"run_ids": [run_id_a, run_id_b]})
    assert resp.status_code == 200
    data = resp.json()

    # Verify top-level keys
    assert "runs" in data
    assert "parameters" in data
    assert "metrics" in data
    assert "diff_summary" in data

    # Verify runs
    assert len(data["runs"]) == 2
    run_ids = [r["id"] for r in data["runs"]]
    assert run_ids == [run_id_a, run_id_b]

    # Verify parameters include our keys
    param_map = {p["name"]: p for p in data["parameters"]}
    assert "lr" in param_map
    assert "epochs" in param_map
    assert "batch_size" in param_map

    # lr and batch_size are different; epochs is same
    assert param_map["lr"]["is_different"] is True
    assert param_map["batch_size"]["is_different"] is True
    assert param_map["epochs"]["is_different"] is False

    # diff_summary
    summary = data["diff_summary"]
    assert summary["total_params"] >= 3
    assert summary["different_params"] >= 2
    assert summary["total_metrics"] == 2
    assert "accuracy" in summary["best_metric_per_key"]
    assert "loss" in summary["best_metric_per_key"]

    # metric row checks
    metric_map = {m["name"]: m for m in data["metrics"]}
    assert "accuracy" in metric_map
    assert "loss" in metric_map

    assert metric_map["accuracy"]["higher_is_better"] is True
    assert metric_map["accuracy"]["best_run_id"] == run_id_b  # 0.88 > 0.85

    assert metric_map["loss"]["higher_is_better"] is False  # heuristic detects lower is better
    assert metric_map["loss"]["best_run_id"] == run_id_b  # 0.20 < 0.25

    # delta from baseline for run_b's accuracy = ((0.88 - 0.85) / 0.85) * 100
    acc_b = metric_map["accuracy"]["values"][run_id_b]
    assert acc_b["delta_from_baseline"] is not None
    assert round(acc_b["delta_from_baseline"], 1) == round((0.88 - 0.85) / 0.85 * 100, 1)


async def test_compare_runs_less_than_two(auth_client: AsyncClient):
    """POST /runs/compare with fewer than 2 run IDs returns 422 (Pydantic validation)."""
    resp = await auth_client.post("/api/v1/runs/compare", json={"run_ids": ["abc"]})
    assert resp.status_code == 422


async def test_compare_runs_missing(auth_client: AsyncClient):
    """POST /runs/compare with nonexistent run IDs returns 404."""
    resp = await auth_client.post(
        "/api/v1/runs/compare",
        json={
            "run_ids": [
                "00000000-0000-0000-0000-000000000000",
                "00000000-0000-0000-0000-000000000001",
            ]
        },
    )
    assert resp.status_code == 404
