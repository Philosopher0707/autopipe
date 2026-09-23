"""JWT Authentication utilities for AutoPipe Dashboard."""

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.config import settings
from app.db.models import User
from app.db.session import get_db
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Proper password hashing using bcrypt
# - Uses adaptive bcrypt with 12 rounds (configurable)
# - Random salt automatically generated per password
# - Resistant to GPU/ASIC brute force attacks
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Legacy SHA256 salt for migration
LEGACY_SALT = "autopipe-dashboard-salt-2024"


def _legacy_hash_password(password: str) -> str:
    """Legacy SHA256 password hashing (for migration)."""
    salted = f"{password}{LEGACY_SALT}"
    return hashlib.sha256(salted.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password.
    Supports both bcrypt (new) and SHA256 (legacy) hashes.
    """
    # Check if it's a bcrypt hash (starts with $2b$ or $2a$)
    if hashed_password.startswith("$"):
        # bcrypt hash
        try:
            return pwd_context.verify(plain_password[:72], hashed_password)
        except Exception:
            return False
    else:
        # Legacy SHA256 row (pre-bcrypt). Kept only until
        # count_legacy_password_hashes() reports 0 everywhere.
        return _legacy_hash_password(plain_password) == hashed_password


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt."""
    # bcrypt has a 72-byte limit; truncate if necessary
    return pwd_context.hash(password[:72])


async def count_legacy_password_hashes(db: AsyncSession) -> int:
    """How many users still hold a non-bcrypt hash — the removal gate.

    Upgrade-on-login rehashes rows lazily, and SHA256→bcrypt is impossible
    in bulk (the plaintext only exists at login). When this returns 0 for a
    deployment, the legacy fallback can be deleted: ``_legacy_hash_password``
    and the non-``$`` branch of ``verify_password``.
    """
    from sqlalchemy import func

    result = await db.execute(
        select(func.count()).select_from(User).where(~User.hashed_password.startswith("$"))
    )
    return int(result.scalar_one())


# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get the current authenticated user from the JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
        )

    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def require_role(*roles: str):
    """Dependency to require specific user roles."""

    async def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role.value not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {roles}",
            )
        return current_user

    return role_checker
