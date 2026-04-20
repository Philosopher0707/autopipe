"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_password_hash
from app.db.models import User


pytestmark = pytest.mark.asyncio


async def test_register_new_user(client: AsyncClient):
    """POST /auth/register creates a new user."""
    resp = await client.post("/api/v1/auth/register", json={
        "username": "newuser",
        "email": "new@example.com",
        "password": "securepass1",
        "role": "viewer",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["username"] == "newuser"
    assert data["email"] == "new@example.com"
    assert "password" not in data
    assert "hashed_password" not in data


async def test_register_duplicate_username(client: AsyncClient, seed_user: User):
    """POST /auth/register with existing username returns error."""
    resp = await client.post("/api/v1/auth/register", json={
        "username": seed_user.username,
        "email": "other@example.com",
        "password": "securepass1",
        "role": "viewer",
    })
    assert resp.status_code in (400, 409)


async def test_login_json_success(client: AsyncClient, seed_user: User):
    """POST /auth/login/json returns a token for valid credentials."""
    resp = await client.post("/api/v1/auth/login/json", json={
        "username": seed_user.username,
        "password": "testpass123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_login_json_wrong_password(client: AsyncClient, seed_user: User):
    """POST /auth/login/json with wrong password returns 401."""
    resp = await client.post("/api/v1/auth/login/json", json={
        "username": seed_user.username,
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


async def test_login_json_nonexistent_user(client: AsyncClient):
    """POST /auth/login/json with unknown user returns 401."""
    resp = await client.post("/api/v1/auth/login/json", json={
        "username": "ghost",
        "password": "anything",
    })
    assert resp.status_code == 401


async def test_get_current_user(client: AsyncClient, auth_headers: dict):
    """GET /auth/me with valid token returns the user."""
    resp = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "testuser"


async def test_get_current_user_no_token(client: AsyncClient):
    """GET /auth/me without token returns 401."""
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


async def test_oauth2_form_login_success(client: AsyncClient, seed_user: User):
    """POST /auth/login (OAuth2 form) returns a token."""
    resp = await client.post("/api/v1/auth/login", data={
        "username": seed_user.username,
        "password": "testpass123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_oauth2_form_login_wrong_password(client: AsyncClient, seed_user: User):
    """POST /auth/login (OAuth2 form) with wrong password returns 401."""
    resp = await client.post("/api/v1/auth/login", data={
        "username": seed_user.username,
        "password": "wrongpass",
    })
    assert resp.status_code == 401


async def test_login_disabled_user(client: AsyncClient, db_session: AsyncSession):
    """POST /auth/login/json rejects disabled user accounts."""
    from app.db.models import UserRole
    user = User(
        id="disabled-user-id",
        username="disableduser",
        email="disabled@example.com",
        hashed_password=get_password_hash("testpass123"),
        role=UserRole.VIEWER,
        is_active=False,
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post("/api/v1/auth/login/json", json={
        "username": "disableduser",
        "password": "testpass123",
    })
    assert resp.status_code == 401


async def test_expired_token_rejected(client: AsyncClient, seed_user: User):
    """GET /auth/me with expired token returns 401."""
    from datetime import timedelta
    from app.core.auth import create_access_token

    expired_token = create_access_token(
        data={"sub": seed_user.id},
        expires_delta=timedelta(seconds=-1),
    )
    resp = await client.get("/api/v1/auth/me", headers={
        "Authorization": f"Bearer {expired_token}",
    })
    assert resp.status_code == 401