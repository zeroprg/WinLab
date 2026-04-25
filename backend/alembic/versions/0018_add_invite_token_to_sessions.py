"""Add invite_token to interview_sessions"""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("interview_sessions") as batch_op:
        batch_op.add_column(
            sa.Column("invite_token", sa.String(64), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("interview_sessions") as batch_op:
        batch_op.drop_column("invite_token")
