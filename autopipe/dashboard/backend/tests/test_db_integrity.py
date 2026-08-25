"""P2: database integrity — unique constraints, FK enforcement, SQLite pragmas."""

import pytest
from app.db.models import Base, Model, ModelVersion, Step
from sqlalchemy import insert, text
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def sync_engine(tmp_path):
    """Sync engine over the same models with pragmas applied like production."""
    from sqlalchemy import create_engine, event

    engine = create_engine(f"sqlite:///{tmp_path / 'integrity.db'}")

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_connection, _):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()

    Base.metadata.create_all(engine)
    return engine


def test_model_version_unique_constraint(sync_engine):
    """Duplicate (model_id, version) must be rejected by the DB, not the UI."""
    with sync_engine.begin() as conn:
        conn.execute(insert(Model).values(id="m1", name="m", framework="sklearn"))
        conn.execute(
            insert(ModelVersion).values(id="v1", model_id="m1", version=1, artifact_path="/tmp/x")
        )
        with pytest.raises(IntegrityError):
            conn.execute(
                insert(ModelVersion).values(
                    id="v2", model_id="m1", version=1, artifact_path="/tmp/y"
                )
            )


def test_foreign_keys_enforced(sync_engine):
    """Steps pointing at nonexistent runs must be rejected (FK pragma ON)."""
    with sync_engine.begin() as conn, pytest.raises(IntegrityError):
        conn.execute(
            insert(Step).values(
                id="s1",
                run_id="no-such-run",
                name="s",
                step_type="PrintStep",
                status="PENDING",
                order_index=0,
            )
        )


def test_pragmas_active_on_connection(sync_engine):
    with sync_engine.connect() as conn:
        fk = conn.execute(text("PRAGMA foreign_keys")).scalar()
        busy = conn.execute(text("PRAGMA busy_timeout")).scalar()
        mode = conn.execute(text("PRAGMA journal_mode")).scalar()
    assert fk == 1
    assert int(busy) == 5000
    assert str(mode).lower() == "wal"


def test_async_engine_applies_pragmas():
    """The production async session engine must register the same hardening."""
    # Assert functionally rather than introspecting listener registration.
    import anyio
    from app.db.session import engine

    async def _check():
        async with engine.connect() as conn:
            fk = (await conn.execute(text("PRAGMA foreign_keys"))).scalar()
            mode = (await conn.execute(text("PRAGMA journal_mode"))).scalar()
            return fk, mode

    fk, mode = anyio.run(_check)
    assert fk == 1, "production engine missing PRAGMA foreign_keys=ON"
    assert str(mode).lower() == "wal"
