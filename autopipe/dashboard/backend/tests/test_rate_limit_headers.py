"""Production-wiring tests for default rate limiting + response headers.

These exercise the real application (`create_application`) with the real
module-global limiter — no monkeypatched dependencies — because the defect
class here is exactly "the wiring claimed by configuration never runs"
(invariant I18).
"""

import pytest
from app.core.config import settings
from app.core.security import _rate_limiter
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clean_limiter():
    _rate_limiter.reset()
    yield
    _rate_limiter.reset()


async def test_data_route_stamps_ratelimit_headers(auth_client: AsyncClient):
    """A successful data-route response carries X-RateLimit-* headers."""
    resp = await auth_client.get("/api/v1/runs")
    assert resp.status_code == 200

    limit = resp.headers.get("X-RateLimit-Limit")
    remaining = resp.headers.get("X-RateLimit-Remaining")
    assert limit == str(settings.RATE_LIMIT_DEFAULT_REQUESTS)
    # First counted request in a clean window: exactly one consumed.
    assert remaining == str(settings.RATE_LIMIT_DEFAULT_REQUESTS - 1)


async def test_unauthenticated_hammering_is_rate_limited(client: AsyncClient, monkeypatch):
    """Rate limit runs BEFORE auth (D1): 401-hammering exhausts the bucket.

    After the default budget is spent, further requests get 429 even though
    they never presented a token — proving the limiter is a router-level
    dependency on data routes, not a side effect of authenticated handlers.
    """
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT_REQUESTS", 2)

    for _ in range(2):
        resp = await client.get("/api/v1/runs")
        assert resp.status_code == 401  # no token: auth rejects, limiter counted

    resp = await client.get("/api/v1/runs")
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") is not None
    assert resp.headers.get("X-RateLimit-Remaining") == "0"
    assert resp.headers.get("X-RateLimit-Limit") == "2"


async def test_401_response_still_carries_headers(client: AsyncClient):
    """Even an auth-rejected response exposes the rate-limit headers."""
    resp = await client.get("/api/v1/runs")
    assert resp.status_code == 401
    assert resp.headers.get("X-RateLimit-Limit") == str(settings.RATE_LIMIT_DEFAULT_REQUESTS)


async def test_auth_routes_use_the_default_limit_too(client: AsyncClient, monkeypatch):
    """/auth is NOT excluded from the default limit (D2).

    Login/register keep their stricter per-endpoint limits on top. The header
    on a login response reflects whichever limiter evaluated last (the stricter
    login bucket overwrites request.state), so we pin the default bucket by
    its 429, not by the first response's header value.
    """
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT_REQUESTS", 1)

    resp = await client.post(
        "/api/v1/auth/login/json",
        json={"username": "nobody", "password": "wrong-password"},
    )
    # First request passes the default limiter (401 from bad creds is fine).
    assert resp.status_code in (400, 401, 404, 422)
    assert resp.headers.get("X-RateLimit-Limit") is not None

    resp = await client.post(
        "/api/v1/auth/login/json",
        json={"username": "nobody", "password": "wrong-password"},
    )
    # Default bucket (limit=1) exhausted — 429 raised before the handler.
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") is not None
    assert resp.headers.get("X-RateLimit-Limit") == "1"
    assert resp.headers.get("X-RateLimit-Remaining") == "0"


async def test_cors_exposes_ratelimit_headers(client: AsyncClient):
    """CORS actually exposes X-RateLimit-* / Retry-After to browsers."""
    resp = await client.get(
        "/api/v1/runs",
        headers={"Origin": "http://localhost:5173"},
    )
    expose = resp.headers.get("access-control-expose-headers", "")
    assert "X-RateLimit-Limit" in expose
    assert "X-RateLimit-Remaining" in expose
    assert "Retry-After" in expose


async def test_headers_survive_on_429_for_data_route(client: AsyncClient, monkeypatch):
    """The 429 raised mid-dependency still exits with headers intact."""
    monkeypatch.setattr(settings, "RATE_LIMIT_DEFAULT_REQUESTS", 1)
    await client.get("/api/v1/runs")  # consumes the only token (401)
    resp = await client.get("/api/v1/runs")
    assert resp.status_code == 429
    assert resp.headers.get("X-RateLimit-Limit") == "1"
    assert resp.headers.get("X-RateLimit-Remaining") == "0"
    assert int(resp.headers.get("Retry-After", "0")) >= 0
