"""Run-number allocation with conflict retry.

A unique ``(pipeline_id, run_number)`` constraint turns the read-max-then-insert
race into an IntegrityError: two concurrent triggers can read the same max
before either commits. This helper re-reads and retries instead of letting the
race surface as a 500. The API layer translates exhaustion into a 409.

The seam ``_next_number`` exists so tests can force a stale read
deterministically and exercise the real retry path.
"""

from typing import Callable, List

from app.db.models import Run
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

MAX_ATTEMPTS = 5


class RunNumberConflictError(RuntimeError):
    """Could not allocate a unique run number after MAX_ATTEMPTS."""


async def _next_number(db: AsyncSession, pipeline_id: str) -> int:
    result = await db.execute(
        select(func.max(Run.run_number)).where(Run.pipeline_id == pipeline_id)
    )
    return int(result.scalar() or 0) + 1


async def insert_runs_numbered(
    db: AsyncSession,
    pipeline_id: str,
    make_runs: Callable[[int], List[Run]],
) -> List[Run]:
    """Insert runs numbered consecutively from the next free run_number.

    ``make_runs(first_number)`` builds the rows for one attempt; it is invoked
    again on every retry because a rolled-back Run object cannot be re-added.
    A rollback expires the session's objects, so ``make_runs`` must only touch
    plain locals (precomputed values), never ORM attributes.
    """
    for _ in range(MAX_ATTEMPTS):
        first = await _next_number(db, pipeline_id)
        runs = make_runs(first)
        db.add_all(runs)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            continue
        for run in runs:
            await db.refresh(run)
        return runs
    raise RunNumberConflictError(
        f"could not allocate a unique run number for pipeline {pipeline_id} "
        f"after {MAX_ATTEMPTS} attempts"
    )
