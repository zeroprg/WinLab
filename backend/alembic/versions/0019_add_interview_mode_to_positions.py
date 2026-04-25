"""Add interview_mode to positions"""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("positions") as batch_op:
        batch_op.add_column(
            sa.Column("interview_mode", sa.String(16), nullable=False, server_default="both")
        )


def downgrade() -> None:
    with op.batch_alter_table("positions") as batch_op:
        batch_op.drop_column("interview_mode")
