"""Production-wiring integration tests for the execution path.

The pre-existing executor unit tests prove the engine's loop against a fixture
database, but nothing proved the *wired* path: HTTP request -> BackgroundTask ->
worker thread -> canonical engine -> database, with the API and the executor
reading **the same database**. That is precisely the seam where the old code
silently diverged (the test override replaced the async session; the executor
kept a separate engine that could not see the rows).

These tests use one real file-backed SQLite database shared by both the async
API session and the sync executor session, and a real HTTP call through the ASGI
app, so the whole path is exercised as production runs it.
"""

import time
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from app.core.auth import create_access_token, get_password_hash
from app.core.config import settings
from app.db.models import Base, Pipeline, Run, RunStatus, Step, StepStatus, User
from app.db.session import get_db
from app.executor import runner
from app.main import create_application
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from autopipe.core.steps import PrintStep

TERMINAL = {RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.CANCELLED}


@pytest.fixture
def shared_database(tmp_path, monkeypatch):
    """A file-backed SQLite DB shared by the async API and the sync executor.

    ``settings.DATABASE_URL`` is pointed at it and the executor's cached session
    factory is cleared, so the production wiring — not a per-test shortcut — is
    what connects the two halves.
    """
    db_path = tmp_path / "wiring.db"
    sync_url = f"sqlite:///{db_path}"
    async_url = f"sqlite+aiosqlite:///{db_path}"

    monkeypatch.setattr(settings, "DATABASE_URL", sync_url)
    monkeypatch.setattr(runner, "_SyncSessionLocal", None)
    monkeypatch.setattr(runner, "_sync_engine", None)

    async_engine = create_async_engine(async_url, echo=False)
    sync_engine = create_engine(sync_url, echo=False)

    wiring = SimpleNamespace(
        async_engine=async_engine,
        sync_engine=sync_engine,
        url=sync_url,
        async_session=async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False),
        sync_session=sessionmaker(sync_engine, expire_on_commit=False),
    )
    yield wiring


async def _seed_user_and_pipeline(wiring, pipeline_config: dict) -> tuple[AsyncClient, object, str]:
    """Create tables, an admin user and a pipeline; return an authed client."""
    async with wiring.async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with wiring.async_session() as session:
        user = User(
            id="wiring-user",
            username="wiring",
            email="wiring@example.com",
            hashed_password=get_password_hash("password123"),
            role="admin",
            is_active=True,
        )
        session.add(user)
        pipeline_id = str(uuid.uuid4())
        session.add(
            Pipeline(
                id=pipeline_id,
                name=pipeline_config.get("name", "wiring-pipeline"),
                config=pipeline_config,
                created_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    app = create_application()

    async def override_get_db():
        async with wiring.async_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    headers = {"Authorization": f"Bearer {create_access_token({'sub': user.id})}"}
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test", headers=headers)
    return client, app, pipeline_id


async def _wait_for_terminal(wiring, run_id: str, timeout: float = 15.0) -> RunStatus:
    """Poll the shared database until the run reaches a terminal state."""
    deadline = time.time() + timeout
    status_value: RunStatus | None = None
    while time.time() < deadline:
        with wiring.sync_session() as db:
            run = db.get(Run, run_id)
            status_value = run.status if run is not None else None
        if status_value in TERMINAL:
            return status_value
        time.sleep(0.05)
    raise AssertionError(f"run {run_id} never reached a terminal state (still {status_value})")


def _steps_for(wiring, run_id: str) -> list[Step]:
    """Read the persisted steps of a run, ordered by position."""
    with wiring.sync_session() as db:
        return db.scalars(
            select(Step).where(Step.run_id == run_id).order_by(Step.order_index)
        ).all()


async def test_triggered_run_executes_end_to_end(shared_database):
    """HTTP -> BackgroundTask -> thread -> canonical engine -> shared DB."""
    wiring = shared_database
    config = {
        "name": "wiring-success",
        "steps": [
            {"name": "first", "type": "print", "params": {"message": "hello"}},
            {
                "name": "second",
                "type": "print",
                "params": {"message": "world"},
                "depends_on": ["first"],
            },
        ],
    }
    client, app, pipeline_id = await _seed_user_and_pipeline(wiring, config)
    try:
        async with client:
            response = await client.post(f"/api/v1/pipelines/{pipeline_id}/runs")
            assert response.status_code == 201, response.text
            run_id = response.json()["id"]

            assert await _wait_for_terminal(wiring, run_id) is RunStatus.SUCCESS

            with wiring.sync_session() as db:
                run = db.get(Run, run_id)
                assert run.started_at is not None
                assert run.completed_at is not None
                assert run.duration_seconds is not None

            steps = _steps_for(wiring, run_id)
            assert [step.name for step in steps] == ["first", "second"]
            assert all(step.status is StepStatus.SUCCESS for step in steps)
    finally:
        app.dependency_overrides.clear()
        await client.aclose()


async def test_named_bindings_are_honored_through_the_real_wiring(shared_database, monkeypatch):
    """Regression for the dual-semantics defect (old Finding 1).

    The dashboard's old execution loop ignored ``inputs:`` and passed
    ``{step_name: value}``; the core passed ``{param: value}``. This test records
    what the step actually receives through the full HTTP->engine path and asserts
    the parameter name is used — proving the wiring now uses the canonical engine.
    """
    wiring = shared_database
    recorded: dict[str, dict] = {}
    original_run = PrintStep.run

    def recording_run(self, **kwargs):
        recorded[self.name] = dict(kwargs)
        return original_run(self, **kwargs)

    monkeypatch.setattr(PrintStep, "run", recording_run)

    config = {
        "name": "wiring-bindings",
        "steps": [
            {"name": "produce", "type": "print", "params": {"message": "x"}},
            {"name": "consume", "type": "print", "inputs": {"payload": "produce"}},
        ],
    }
    client, app, pipeline_id = await _seed_user_and_pipeline(wiring, config)
    try:
        async with client:
            response = await client.post(f"/api/v1/pipelines/{pipeline_id}/runs")
            assert response.status_code == 201, response.text
            run_id = response.json()["id"]

            assert await _wait_for_terminal(wiring, run_id) is RunStatus.SUCCESS

            assert "consume" in recorded, "the consume step must have executed"
            assert set(recorded["consume"]) == {"payload"}, (
                "named binding must arrive under its parameter name; got "
                f"{recorded['consume']!r} (the old loop would have sent "
                "{'produce': ...})"
            )
    finally:
        app.dependency_overrides.clear()
        await client.aclose()


async def test_failing_step_is_failed_not_stranded(shared_database, monkeypatch):
    """Regression for worker-exception containment (old Finding 2).

    A step that raises must move the run to FAILED with an explanatory message —
    never leave it claiming RUNNING — even when the run is launched over HTTP.
    """
    wiring = shared_database
    original_run = PrintStep.run

    def exploding_run(self, **kwargs):
        if self.name == "bad":
            raise RuntimeError("injected step failure")
        return original_run(self, **kwargs)

    monkeypatch.setattr(PrintStep, "run", exploding_run)

    config = {
        "name": "wiring-failure",
        "steps": [
            {"name": "ok", "type": "print", "params": {"message": "hi"}},
            {"name": "bad", "type": "print", "depends_on": ["ok"]},
            {"name": "after", "type": "print", "depends_on": ["bad"]},
        ],
    }
    client, app, pipeline_id = await _seed_user_and_pipeline(wiring, config)
    try:
        async with client:
            response = await client.post(f"/api/v1/pipelines/{pipeline_id}/runs")
            assert response.status_code == 201, response.text
            run_id = response.json()["id"]

            assert await _wait_for_terminal(wiring, run_id) is RunStatus.FAILED

            with wiring.sync_session() as db:
                run = db.get(Run, run_id)
                assert "bad" in (run.error_message or "")
                assert "injected step failure" in (run.error_message or "")

            steps = _steps_for(wiring, run_id)
            assert [s.status for s in steps] == [
                StepStatus.SUCCESS,
                StepStatus.FAILED,
                StepStatus.SKIPPED,
            ]
    finally:
        app.dependency_overrides.clear()
        await client.aclose()
