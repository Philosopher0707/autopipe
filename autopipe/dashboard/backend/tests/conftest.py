"""Shared test fixtures for the AutoPipe Dashboard backend."""

import asyncio
import time
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from app.core.auth import create_access_token, get_password_hash
from app.core.config import settings
from app.core.security import _rate_limiter
from app.db.models import Base, Experiment, Model, Pipeline, Run, RunStatus, User
from app.db.session import get_db
from app.executor import runner as executor_runner
from app.main import create_application
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

TERMINAL_RUN_STATUSES = {RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.CANCELLED}


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Clear the module-global rate limiter around every test.

    The default limiter now runs on all HTTP routes; without a reset, counters
    accumulate across tests (one client key) and later tests would see 429s.
    """
    _rate_limiter.reset()
    yield
    _rate_limiter.reset()


@pytest_asyncio.fixture
async def engine(tmp_path, monkeypatch) -> AsyncGenerator:
    """Per-test file-backed SQLite shared by the API session *and* the executor.

    The executor reads ``settings.DATABASE_URL`` when it builds its sync session
    factory, so an in-memory API engine meant every dispatching test asserted on
    a database the worker could never see: execution claims were untestable and
    runs leaked toward the real dashboard file. Point both halves at one tmp file
    (the pattern from ``test_executor_integration``) and reset the executor's
    cached factory so each test rebuilds it against that file.
    """
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setattr(executor_runner, "_SyncSessionLocal", None)
    monkeypatch.setattr(executor_runner, "_sync_engine", None)

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False, poolclass=NullPool)

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine

    # Drain executor threads spawned by this test (tracked from execute_run,
    # before Thread.start) so drop_all never races a worker's terminal write.
    deadline = time.monotonic() + 5.0
    while executor_runner._live_threads and time.monotonic() < deadline:
        await asyncio.sleep(0.05)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def wait_terminal(engine):
    """Wait until a run reaches a terminal state in the shared database.

    Uses a fresh session per poll so a long-lived read transaction never holds
    back the executor's writer (WAL readers still see a fixed snapshot).
    """

    async def _wait(run_id: str, timeout: float = 15.0) -> RunStatus:
        maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        deadline = time.monotonic() + timeout
        status: RunStatus | None = None
        while time.monotonic() < deadline:
            async with maker() as session:
                run = await session.get(Run, str(run_id))
                status = run.status if run is not None else None
            if status in TERMINAL_RUN_STATUSES:
                return status
            await asyncio.sleep(0.05)
        raise AssertionError(f"run {run_id} never reached a terminal state (still {status})")

    return _wait


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
