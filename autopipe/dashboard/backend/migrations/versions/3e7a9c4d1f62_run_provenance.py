"""runs: add provenance JSON snapshot (engine/env/code/origin/seeds)

Revision ID: 3e7a9c4d1f62
Revises: b7e4c2a91f03
Create Date: 2026-09-22 00:00:00.000000

"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3e7a9c4d1f62"
down_revision: str | None = "b7e4c2a91f03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("provenance", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.drop_column("provenance")
