"""Add session_id column to messages table"""

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("session_id", sa.String(length=64), nullable=True),
    )
    op.create_foreign_key(
        "fk_messages_session_id",
        "messages",
        "interview_sessions",
        ["session_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_messages_session_id")
    op.drop_constraint("fk_messages_session_id", "messages", type_="foreignkey")
    op.drop_column("messages", "session_id")
