"""Add locale to positions table"""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("positions") as batch_op:
        batch_op.add_column(
            sa.Column("locale", sa.String(8), nullable=True, server_default="ru")
        )


def downgrade() -> None:
    with op.batch_alter_table("positions") as batch_op:
        batch_op.drop_column("locale")
