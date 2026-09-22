"""runs: add config_hash; unique (pipeline_id, run_number)

Revision ID: b7e4c2a91f03
Revises: dfbef38942fc
Create Date: 2026-09-22 00:00:00.000000

"""

from typing import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e4c2a91f03"
down_revision: str | None = "dfbef38942fc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("config_hash", sa.String(length=64), nullable=True))
        batch_op.create_unique_constraint(
            "uq_run_pipeline_run_number", ["pipeline_id", "run_number"]
        )


def downgrade() -> None:
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.drop_constraint("uq_run_pipeline_run_number", type_="unique")
        batch_op.drop_column("config_hash")
