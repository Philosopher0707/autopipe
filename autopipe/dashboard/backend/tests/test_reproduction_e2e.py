"""Phase E/C: full-path reproduction — same config twice yields identical evidence.

Runs one seeded config (file CSV loader + builtin loader + chart-producing
visualize) twice through the real HTTP → admission → runner → engine path and
compares the durable reproduction evidence: config hash, applied seed,
dataset identities (content hashes), produced-artifact content hashes, and
the persisted metric series (MetricLog rows).

The deterministic metric producers are the config's own loaders: both emit
only local-input-derived scalars via ``Step.log_metrics`` (row/column counts,
byte usage of the fixed CSV / builtin iris) — no network, LLM, wall-clock,
or process-global RNG involved.
"""

from pathlib import Path

from app.db.models import Artifact, MetricLog, Run, RunStatus, Step
from httpx import AsyncClient
from sqlalchemy import select


async def _run_once(
    auth_client: AsyncClient,
    pipeline_id: str,
    db_session,
    wait_terminal,
    csv_path: Path,
):
    resp = await auth_client.post(
        f"/api/v1/pipelines/{pipeline_id}/runs",
        json={
            "config_override": {
                "name": "repro-e2e",
                "seed": 42,
                "steps": [
                    {
                        "name": "load",
                        "type": "data_loader",
                        "params": {"source": str(csv_path), "format": "csv"},
                    },
                    {"name": "sample", "type": "sample_data_loader"},
                ],
            }
        },
    )
    assert resp.status_code == 201, resp.text
    run_id = resp.json()["id"]
    assert await wait_terminal(run_id) is RunStatus.SUCCESS

    db_session.expire_all()
    run = await db_session.get(Run, run_id)
    assert run is not None
    rows = (
        (await db_session.execute(select(Artifact).where(Artifact.run_id == run_id)))
        .scalars()
        .all()
    )
    metric_rows = (
        await db_session.execute(
            select(MetricLog, Step.name)
            .join(Step, MetricLog.step_id == Step.id)
            .where(MetricLog.run_id == run_id)
        )
    ).all()
    # Comparable metric series. Included: step execution order (step_index),
    # step name (config identity), metric_name and value — every persisted
    # deterministic field that distinguishes the series. Excluded: id / run_id /
    # step_id (generated per-run row ids) and recorded_at (wall clock);
    # pipeline_id / experiment_id are constant FKs, not series content.
    # Sorted into canonical order because MetricLog persists no within-step
    # emission-order column — canonicalization for comparison only; values
    # are compared exactly, with no rounding or tolerance.
    series = sorted(
        (m.step_index, step_name, m.metric_name, m.value) for m, step_name in metric_rows
    )
    return {
        "config_hash": run.config_hash,
        "provenance": dict(run.provenance or {}),
        "artifact_sha256": sorted(r.sha256 for r in rows if r.sha256),
        "artifact_count": len(rows),
        "metrics": series,
    }


async def test_same_config_twice_reproduces_identical_evidence(
    auth_client: AsyncClient,
    seed_pipeline,
    db_session,
    wait_terminal,
    tmp_path,
    monkeypatch,
):
    import matplotlib

    matplotlib.use("Agg")
    monkeypatch.chdir(tmp_path)

    csv_path = tmp_path / "input.csv"
    csv_path.write_bytes(b"feature,target\n1,0\n2,1\n3,0\n4,1\n5,0\n")
    pipeline_id = seed_pipeline.id  # capture before expire_all detaches the fixture

    first = await _run_once(auth_client, pipeline_id, db_session, wait_terminal, csv_path)
    second = await _run_once(auth_client, pipeline_id, db_session, wait_terminal, csv_path)

    # Config identity: same bytes in, same admitted config out.
    assert first["config_hash"] == second["config_hash"]
    assert first["config_hash"] is not None

    # Seed: DECLARED and APPLIED on both runs.
    for snap in (first, second):
        assert snap["provenance"].get("seeds") == {"seed": 42}
        assert snap["provenance"].get("seed_applied") == 42

    # Dataset identity: identical entries, including the file content hash.
    ds1, ds2 = first["provenance"]["datasets"], second["provenance"]["datasets"]
    assert ds1 == ds2
    file_entries = [e for e in ds1 if e["kind"] == "file" and e["source"].endswith("input.csv")]
    assert len(file_entries) == 1
    assert file_entries[0]["sha256"] and file_entries[0]["sha256"] != "unavailable"
    assert any(e["kind"] == "builtin" for e in ds1)

    # Artifact identity: produced charts registered with identical content hashes.
    assert first["artifact_count"] > 0, "visualize must have produced registered charts"
    assert first["artifact_sha256"] == second["artifact_sha256"]

    # Metric series: identity (names), step identity, execution ordering, and
    # exact values all reproduce across runs.
    assert first["metrics"], "loader steps must have persisted a metric series"
    assert {m[2] for m in first["metrics"]} == {
        "rows_loaded",
        "columns_loaded",
        "memory_usage_mb",  # data_loader ("load")
        "rows",
        "columns",  # sample_data_loader ("sample")
    }
    assert {m[1] for m in first["metrics"]} == {"load", "sample"}
    assert {m[0] for m in first["metrics"] if m[1] == "load"} == {0}
    assert {m[0] for m in first["metrics"] if m[1] == "sample"} == {1}
    assert first["metrics"] == second["metrics"]
