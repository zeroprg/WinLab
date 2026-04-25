"""Add display_name to users table"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "display_name")
