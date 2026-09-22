"""Authentication endpoints."""

from datetime import datetime, timezone
from typing import Optional

from app.core.auth import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.core.config import settings
from app.core.security import check_login_rate_limit, check_register_rate_limit
from app.db.models import User
from app.db.session import get_db
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


# ==================== Request/Response Schemas ====================


class Token(BaseModel):
    """Token response schema."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenData(BaseModel):
    """Decoded token data."""

    user_id: Optional[str] = None


class UserCreate(BaseModel):
    """User creation schema."""

    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=100)
    full_name: Optional[str] = Field(None, max_length=255)
    role: str = Field(default="viewer")


class UserResponse(BaseModel):
    """User response schema (safe - no password)."""

    id: str
    username: str
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    last_login: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """User update schema."""

    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class LoginRequest(BaseModel):
    """Login request with explicit fields."""

    username: str
    password: str


# ==================== Auth Endpoints ====================


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """Login with username and password. Returns JWT access token."""
    # Check rate limit
    check_login_rate_limit(request)

    # Find user
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
        )

    # Update last login; transparently upgrade legacy SHA256 to bcrypt
    if not user.hashed_password.startswith("$"):
        user.hashed_password = get_password_hash(form_data.password)
    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    # Create token
    access_token = create_access_token(
        data={"sub": user.id, "username": user.username, "role": user.role.value}
    )

    return Token(
        access_token=access_token,
        token_type="bearer",  # nosec B106 — OAuth2 token-type string (RFC 6750), not a password
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/login/json", response_model=Token)
async def login_json(
    credentials: LoginRequest,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """Login with JSON body instead of form data."""
    # Check rate limit
    check_login_rate_limit(request)

    # Find user
    result = await db.execute(select(User).where(User.username == credentials.username))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
        )

    # Update last login; transparently upgrade legacy SHA256 to bcrypt
    if not user.hashed_password.startswith("$"):
        user.hashed_password = get_password_hash(credentials.password)
    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    # Create token
    access_token = create_access_token(
        data={"sub": user.id, "username": user.username, "role": user.role.value}
    )

    return Token(
        access_token=access_token,
        token_type="bearer",  # nosec B106 — OAuth2 token-type string (RFC 6750), not a password
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """Get the current authenticated user's information."""
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role.value,
        is_active=current_user.is_active,
        last_login=current_user.last_login,
        created_at=current_user.created_at,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    request: Request = None,
):
    """Register a new user account."""
    # Check rate limit
    check_register_rate_limit(request)

    # Check if username exists
    result = await db.execute(select(User).where(User.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    # Check if email exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Role is NEVER client-controlled: open registration granting arbitrary
    # roles was a privilege-escalation hole. The very first account bootstraps
    # as admin; every later account starts as data_scientist and must be
    # promoted by an existing admin.
    from app.db.models import UserRole

    count_result = await db.execute(select(func.count(User.id)))
    is_first_user = (count_result.scalar() or 0) == 0
    role = UserRole.ADMIN if is_first_user else UserRole.DATA_SCIENTIST

    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=role,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        is_active=user.is_active,
        last_login=user.last_login,
        created_at=user.created_at,
    )
