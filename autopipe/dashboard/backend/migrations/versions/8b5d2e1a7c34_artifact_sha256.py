"""artifacts + chart_artifacts: add sha256 content address

Revision ID: 8b5d2e1a7c34
Revises: 3e7a9c4d1f62
Create Date: 2026-09-22 00:00:00.000000

"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8b5d2e1a7c34"
down_revision: str | None = "3e7a9c4d1f62"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("artifacts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("sha256", sa.String(length=64), nullable=True))
    with op.batch_alter_table("chart_artifacts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("sha256", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chart_artifacts", schema=None) as batch_op:
        batch_op.drop_column("sha256")
    with op.batch_alter_table("artifacts", schema=None) as batch_op:
        batch_op.drop_column("sha256")
