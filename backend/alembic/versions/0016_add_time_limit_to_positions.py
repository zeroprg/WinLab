"""Add time_limit_minutes to positions table"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("positions") as batch_op:
        batch_op.add_column(
            sa.Column("time_limit_minutes", sa.Float(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("positions") as batch_op:
        batch_op.drop_column("time_limit_minutes")
