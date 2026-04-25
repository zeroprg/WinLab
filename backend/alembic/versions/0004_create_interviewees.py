"""Create interviewees table"""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interviewees",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("position_id", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=False),
        sa.Column("last_name", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False, unique=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("source", sa.String(length=128), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_interviewees_user_id", "interviewees", ["user_id"], unique=True)
    op.create_index("ix_interviewees_position_id", "interviewees", ["position_id"])
    op.create_index("ix_interviewees_email", "interviewees", ["email"])
    op.create_index("ix_interviewees_status", "interviewees", ["status"])


def downgrade() -> None:
    op.drop_index("ix_interviewees_status")
    op.drop_index("ix_interviewees_email")
    op.drop_index("ix_interviewees_position_id")
    op.drop_index("ix_interviewees_user_id")
    op.drop_table("interviewees")
