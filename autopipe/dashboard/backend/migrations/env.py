"""Alembic migration environment for the AutoPipe dashboard database.

Usage (from autopipe/dashboard/backend):

    alembic upgrade head          # apply migrations (fresh installs)
    alembic stamp head            # adopt existing create_all databases
    alembic revision --autogenerate -m "..."   # new migration

The URL comes from app settings so migrations always target the same
database the application uses. SQLite async URLs are converted to their
sync driver form, which Alembic runs under.
"""

from logging.config import fileConfig

from alembic import context
from app.core.config import settings
from app.db.models import Base
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    url = settings.DATABASE_URL
    # Alembic runs synchronously; map async driver URLs to sync equivalents.
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite:///")
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://")
    return url


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url_is_sqlite(),
    )
    with context.begin_transaction():
        context.run_migrations()


def url_is_sqlite() -> bool:
    return _database_url().startswith("sqlite")


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Batch mode: required for ALTERs on SQLite (table rebuild).
            render_as_batch=url_is_sqlite(),
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
