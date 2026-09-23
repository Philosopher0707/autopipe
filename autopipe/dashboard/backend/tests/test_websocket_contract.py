"""WS broadcast contract: every message is the envelope {type, data, timestamp}.

Routing (run:{id} vs dashboard) is server-side; clients dispatch on ``type``
only. All payload fields live inside ``data`` — no top-level payload keys
besides the envelope. Regression lock for the frontend's WSMessage shape.
"""

import json
from datetime import datetime
from typing import Any, Dict, List

import pytest
from app.api.v1.endpoints.websocket import (
    broadcast_drift_alert,
    broadcast_model_promoted,
    broadcast_run_log,
    broadcast_run_metric,
    broadcast_run_status,
    manager,
)

pytestmark = pytest.mark.asyncio

ENVELOPE_KEYS = {"type", "data", "timestamp"}


class FakeWS:
    def __init__(self) -> None:
        self.sent: List[Dict[str, Any]] = []

    async def send_text(self, text: str) -> None:
        self.sent.append(json.loads(text))


async def _subscribe(channel: str) -> FakeWS:
    ws = FakeWS()
    manager.channels.setdefault(channel, set()).add(ws)
    manager.connections[ws] = {channel}
    return ws


@pytest.fixture(autouse=True)
def clean_manager():
    saved_channels = {k: set(v) for k, v in manager.channels.items()}
    saved_conns = {k: set(v) for k, v in manager.connections.items()}
    manager.channels.clear()
    manager.connections.clear()
    yield
    manager.channels.clear()
    manager.connections.clear()
    manager.channels.update(saved_channels)
    manager.connections.update(saved_conns)


async def test_run_status_envelope():
    run_ws = await _subscribe("run:r1")
    dash_ws = await _subscribe("dashboard")

    await broadcast_run_status("r1", "SUCCESS", {"extra": 1})

    for ws in (run_ws, dash_ws):
        assert len(ws.sent) == 1
        msg = ws.sent[0]
        assert set(msg) == ENVELOPE_KEYS, f"payload leaked to top level: {set(msg)}"
        assert msg["type"] == "run.status"
        assert msg["data"]["run_id"] == "r1"
        assert msg["data"]["status"] == "SUCCESS"
        assert msg["data"]["extra"] == 1
        datetime.fromisoformat(msg["timestamp"])
    # Dashboard copy is byte-identical — no mutating channel annotation.
    assert run_ws.sent[0] == dash_ws.sent[0]


async def test_run_log_envelope():
    ws = await _subscribe("run:r1")
    await broadcast_run_log("r1", "step-a", "ERROR", "boom")

    msg = ws.sent[0]
    assert set(msg) == ENVELOPE_KEYS
    assert msg["type"] == "run.log"
    assert msg["data"] == {
        "run_id": "r1",
        "step_id": "step-a",
        "level": "ERROR",
        "message": "boom",
    }


async def test_run_metric_envelope():
    ws = await _subscribe("run:r1")
    await broadcast_run_metric("r1", "step-a", "accuracy", 0.9, step_number=3)

    msg = ws.sent[0]
    assert set(msg) == ENVELOPE_KEYS
    assert msg["type"] == "run.metric"
    assert msg["data"] == {
        "run_id": "r1",
        "step_id": "step-a",
        "metric_name": "accuracy",
        "value": 0.9,
        "step_number": 3,
    }


async def test_drift_alert_envelope_on_dashboard_channel():
    ws = await _subscribe("dashboard")
    await broadcast_drift_alert("alert-1", "age", "warning", "PSI drift detected")

    msg = ws.sent[0]
    assert set(msg) == ENVELOPE_KEYS
    assert msg["type"] == "drift.alert"
    assert msg["data"] == {
        "alert_id": "alert-1",
        "feature_name": "age",
        "severity": "warning",
        "message": "PSI drift detected",
    }


async def test_model_promoted_envelope_on_dashboard_channel():
    ws = await _subscribe("dashboard")
    await broadcast_model_promoted("m1", 2, "staging", "production")

    msg = ws.sent[0]
    assert set(msg) == ENVELOPE_KEYS
    assert msg["type"] == "model.promoted"
    assert msg["data"] == {
        "model_id": "m1",
        "version": 2,
        "from_stage": "staging",
        "to_stage": "production",
    }
