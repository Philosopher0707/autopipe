"""Shared test fixtures for the AutoPipe Dashboard backend."""

from typing import AsyncGenerator

import pytest_asyncio
from app.core.auth import create_access_token, get_password_hash
from app.db.models import Base, Experiment, Model, Pipeline, User
from app.db.session import get_db
from app.main import create_application
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def engine():
    """Create a fresh in-memory SQLite engine with tables for each test."""
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session for tests."""
    TestSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Provide an HTTP test client with DB dependency override."""
    app = create_application()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# --- Seed fixtures ---


@pytest_asyncio.fixture
async def seed_user(db_session: AsyncSession) -> User:
    """Create a test user and return it."""
    user = User(
        id="test-user-id",
        username="testuser",
        email="test@example.com",
        hashed_password=get_password_hash("testpass123"),
        role="admin",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(seed_user: User) -> dict:
    """Return authorization headers with a valid JWT for the seed user."""
    token = create_access_token(data={"sub": seed_user.id})
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_client(
    db_session: AsyncSession, seed_user: User, auth_headers: dict
) -> AsyncGenerator[AsyncClient, None]:
    """HTTP client that authenticates as the seeded admin on every request."""
    app = create_application()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=auth_headers) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seed_pipeline(db_session: AsyncSession) -> Pipeline:
    """Create a test pipeline and return it."""
    pipeline = Pipeline(
        name="test-pipeline",
        description="A pipeline for testing",
        config={"steps": [{"name": "step1", "type": "print", "params": {"message": "hello"}}]},
        tags=["test"],
    )
    db_session.add(pipeline)
    await db_session.commit()
    await db_session.refresh(pipeline)
    return pipeline


@pytest_asyncio.fixture
async def seed_experiment(db_session: AsyncSession) -> Experiment:
    """Create a test experiment and return it."""
    experiment = Experiment(
        name="test-experiment",
        description="An experiment for testing",
        config={"search_space": {"lr": {"type": "float", "low": 0.001, "high": 0.1}}},
        tags=["test"],
    )
    db_session.add(experiment)
    await db_session.commit()
    await db_session.refresh(experiment)
    return experiment


@pytest_asyncio.fixture
async def seed_model(db_session: AsyncSession) -> Model:
    """Create a test model and return it."""
    model = Model(
        name="test-model",
        description="A model for testing",
        framework="sklearn",
        task_type="classification",
    )
    db_session.add(model)
    await db_session.commit()
    await db_session.refresh(model)
    return model
