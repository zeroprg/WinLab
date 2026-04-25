"""Create interview_sessions table"""

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_sessions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("interviewee_id", sa.String(length=64), nullable=False),
        sa.Column("session_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="in_progress"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("prompt_used", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["interviewee_id"], ["interviewees.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_sessions_interviewee", "interview_sessions", ["interviewee_id"])
    op.create_index("ix_sessions_status", "interview_sessions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_sessions_status")
    op.drop_index("ix_sessions_interviewee")
    op.drop_table("interview_sessions")
