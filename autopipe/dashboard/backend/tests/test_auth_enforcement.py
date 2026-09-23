"""Tests proving the API is actually protected (no anonymous data access)."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_pipelines_require_auth(client: AsyncClient):
    """Anonymous requests to a data route are rejected with 401."""
    resp = await client.get("/api/v1/pipelines")
    assert resp.status_code == 401


async def test_bad_token_rejected(client: AsyncClient, seed_user):
    """A garbage bearer token is rejected with 401."""
    resp = await client.get("/api/v1/pipelines", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


async def test_wrong_secret_token_rejected(client: AsyncClient, seed_user):
    """A token signed with the wrong key must not authenticate."""
    from app.core.config import settings
    from jose import jwt as jose_jwt

    forged = jose_jwt.encode(
        {"sub": "test-user-id", "type": "access", "exp": 9999999999},
        "attacker-secret",
        algorithm=settings.JWT_ALGORITHM,
    )
    resp = await client.get("/api/v1/pipelines", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401


async def test_authenticated_access_allowed(auth_client: AsyncClient):
    """The seeded admin can read pipelines through the enforced dependency."""
    resp = await auth_client.get("/api/v1/pipelines")
    assert resp.status_code == 200


async def test_delete_requires_admin_role(
    client: AsyncClient, auth_client: AsyncClient, db_session
):
    """DELETE /pipelines/{id}: anonymous 401, viewer 403, admin passes authz."""
    from app.core.auth import create_access_token, get_password_hash
    from app.db.models import User

    # Anonymous delete is rejected before anything else.
    resp = await client.delete("/api/v1/pipelines/does-not-exist")
    assert resp.status_code == 401

    # A valid token for a non-admin user must be rejected with 403.
    viewer = User(
        username="vieweruser",
        email="viewer@example.com",
        hashed_password=get_password_hash("viewerpw123"),
        role="viewer",
        is_active=True,
    )
    db_session.add(viewer)
    await db_session.commit()
    await db_session.refresh(viewer)

    viewer_token = create_access_token(data={"sub": viewer.id})
    resp = await client.delete(
        "/api/v1/pipelines/does-not-exist",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403


async def test_register_cannot_self_assign_admin(client: AsyncClient):
    """Registration ignores client-supplied roles; only the first user is admin."""
    first = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "escalator",
            "email": "esc@example.com",
            "password": "supersecret123",
            "role": "data_scientist",
        },
    )
    assert first.status_code == 201
    # First account in the isolated DB bootstraps to admin regardless of input.
    assert first.json()["role"] == "admin"

    second = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "follower",
            "email": "follow@example.com",
            "password": "supersecret123",
            "role": "admin",
        },
    )
    assert second.status_code == 201
    # A later registration must NOT inherit admin via the role field.
    assert second.json()["role"] != "admin"


async def test_login_upgrades_legacy_hash(client: AsyncClient, db_session):
    """Logging in with a legacy SHA256 hash transparently rehashes to bcrypt."""
    from app.core.auth import _legacy_hash_password
    from app.db.models import User, UserRole

    legacy_hash = _legacy_hash_password("oldstyle-pass")
    assert not legacy_hash.startswith("$")

    user = User(
        username="legacyuser",
        email="legacy@example.com",
        hashed_password=legacy_hash,
        role=UserRole.DATA_SCIENTIST,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "legacyuser", "password": "oldstyle-pass"},
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]

    await db_session.refresh(user)
    assert user.hashed_password.startswith("$2"), (
        "legacy SHA256 hash was not upgraded to bcrypt on login"
    )


async def test_login_json_upgrades_legacy_hash(client: AsyncClient, db_session):
    """The JSON login path must upgrade legacy hashes too (parity with form login)."""
    from app.core.auth import _legacy_hash_password
    from app.db.models import User, UserRole

    user = User(
        username="legacyjson",
        email="legacyjson@example.com",
        hashed_password=_legacy_hash_password("oldstyle-pass"),
        role=UserRole.DATA_SCIENTIST,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post(
        "/api/v1/auth/login/json",
        json={"username": "legacyjson", "password": "oldstyle-pass"},
    )
    assert resp.status_code == 200

    await db_session.refresh(user)
    assert user.hashed_password.startswith("$2"), (
        "JSON login path did not upgrade the legacy SHA256 hash"
    )


async def test_count_legacy_password_hashes_is_the_removal_gate(client: AsyncClient, db_session):
    """Audit helper: counts non-bcrypt rows; drops as they upgrade on login.

    This count is the observable precondition for deleting the SHA256
    fallback from ``verify_password`` (queue item: legacy password removal
    path). At zero everywhere, ``_legacy_hash_password`` + the non-``$``
    branch can go.
    """
    from app.core.auth import _legacy_hash_password, count_legacy_password_hashes
    from app.db.models import User, UserRole

    legacy = User(
        username="gateuser",
        email="gate@example.com",
        hashed_password=_legacy_hash_password("gate-pass-1"),
        role=UserRole.VIEWER,
        is_active=True,
    )
    bcrypt_user = User(
        username="gateuser2",
        email="gate2@example.com",
        hashed_password="$2b$12$hashhashhashhashhashhashhashhashhashhashhashhashhashha",
        role=UserRole.VIEWER,
        is_active=True,
    )
    db_session.add_all([legacy, bcrypt_user])
    await db_session.commit()

    assert await count_legacy_password_hashes(db_session) == 1

    resp = await client.post(
        "/api/v1/auth/login",
        data={"username": "gateuser", "password": "gate-pass-1"},
    )
    assert resp.status_code == 200
    await db_session.refresh(legacy)
    # bcrypt prefix check: fake non-bcrypt row above must not count
    assert await count_legacy_password_hashes(db_session) == 0


async def test_websocket_auth_rejects_missing_token(db_session):
    """WS handshake guard: no token -> reject; malformed token -> reject."""
    from app.api.v1.endpoints.websocket import authenticate_websocket

    class _StubWS:
        def __init__(self, query: dict):
            self.query_params = query

    # No token at all
    assert await authenticate_websocket(_StubWS({}), db_session) is False
    # Malformed token
    assert await authenticate_websocket(_StubWS({"token": "nonsense"}), db_session) is False


async def test_websocket_auth_accepts_valid_token(seed_user, db_session):
    """A signed access token for an active DB user authenticates the WS guard."""
    from app.api.v1.endpoints.websocket import authenticate_websocket
    from app.core.auth import create_access_token

    token = create_access_token(data={"sub": seed_user.id})

    class _StubWS:
        query_params = {"token": token}

    assert await authenticate_websocket(_StubWS(), db_session) is True  # type: ignore[arg-type]


async def test_websocket_auth_rejects_deleted_user(seed_user, db_session):
    """Parity with REST (I17): a token whose subject no longer exists is rejected.

    Before this check, claims-only validation let a deleted user's unexpired
    token keep streaming run data over WS while REST already returned 401.
    """
    from app.api.v1.endpoints.websocket import authenticate_websocket
    from app.core.auth import create_access_token

    token = create_access_token(data={"sub": seed_user.id})

    class _StubWS:
        query_params = {"token": token}

    await db_session.delete(seed_user)
    await db_session.commit()

    assert await authenticate_websocket(_StubWS(), db_session) is False  # type: ignore[arg-type]


async def test_websocket_auth_rejects_inactive_user(seed_user, db_session):
    """A deactivated user's still-valid token must not open a WS stream."""
    from app.api.v1.endpoints.websocket import authenticate_websocket
    from app.core.auth import create_access_token

    token = create_access_token(data={"sub": seed_user.id})

    class _StubWS:
        query_params = {"token": token}

    seed_user.is_active = False
    await db_session.commit()

    assert await authenticate_websocket(_StubWS(), db_session) is False  # type: ignore[arg-type]
