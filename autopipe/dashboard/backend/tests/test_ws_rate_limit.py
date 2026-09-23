"""WS handshake counts against the default per-peer rate-limit bucket (D3).

Production-wiring tests (I18): real app, real module-global limiter — the
defect class is "the wiring claimed by configuration never runs". Sync
because Starlette's TestClient owns its own event loop for handshakes.

Before the fix, an exhausted bucket still reached ``authenticate_websocket``
(close 1008) — the handshake never consulted the limiter.
"""

import pytest
from app.core.config import settings
from app.core.security import _rate_limiter
from app.db.session import get_db
from app.main import create_application
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

WS_URL = "/api/v1/ws/dashboard"


@pytest.fixture
def ws_client():
    """Real app with the DB dependency stubbed (auth rejects before use)."""
    app = create_application()

    async def _no_db():
        yield None  # token-less handshakes return before touching the session

    app.dependency_overrides[get_db] = _no_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _handshake(client: TestClient) -> int:
    """Attempt one handshake; return the disconnect code observed."""
    try:
        with client.websocket_connect(WS_URL):
            return -1  # connected: never expected in these tests
    except WebSocketDisconnect as exc:
        return exc.code


def test_ws_handshake_spends_the_shared_default_bucket(ws_client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT_REQUESTS", 1)

    # First handshake passes the limiter (count=1) and is rejected by auth.
    assert _handshake(ws_client) == 1008

    # Bucket exhausted: the next handshake is refused by the limiter (1013),
    # NOT by auth — the wiring red-state observed 1008 here.
    assert _handshake(ws_client) == 1013

    # Same peer, same budget: HTTP now sees the exhausted bucket too.
    resp = ws_client.get("/api/v1/runs")
    assert resp.status_code == 429
    assert resp.headers.get("X-RateLimit-Remaining") == "0"


def test_ws_handshake_not_limited_on_a_fresh_bucket(ws_client, monkeypatch):
    """Control: default budget intact → handshake reaches auth, not the limiter."""
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT_REQUESTS", 100)
    _rate_limiter.reset()

    assert _handshake(ws_client) == 1008  # auth rejection, not 1013
