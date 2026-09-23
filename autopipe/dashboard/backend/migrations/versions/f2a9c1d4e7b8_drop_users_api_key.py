"""drop dead users.api_key column

Revision ID: f2a9c1d4e7b8
Revises: 8b5d2e1a7c34
Create Date: 2026-09-23 00:00:00.000000

"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a9c1d4e7b8"
down_revision: str | None = "8b5d2e1a7c34"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Zero accessors/serialization ever read users.api_key (dead since schema
    # creation). Batch rebuild also drops the unnamed UNIQUE(api_key).
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("api_key")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("api_key", sa.String(), nullable=True))
        batch_op.create_unique_constraint(None, ["api_key"])
