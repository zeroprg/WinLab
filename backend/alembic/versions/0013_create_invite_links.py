"""Create invite_links table"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invite_links",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("token", sa.String(32), nullable=False, unique=True, index=True),
        sa.Column(
            "position_id",
            sa.String(64),
            sa.ForeignKey("positions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("candidate_email", sa.String(255), nullable=True),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("used_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("invite_links")
