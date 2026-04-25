"""Create interview_prompts table"""

import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "interview_prompts",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("position_id", sa.String(length=64), nullable=True),
        sa.Column("interviewee_id", sa.String(length=64), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["interviewee_id"], ["interviewees.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "position_id IS NOT NULL OR interviewee_id IS NOT NULL",
            name="ck_prompt_has_owner",
        ),
    )
    op.create_index("ix_prompts_position_id", "interview_prompts", ["position_id"])
    op.create_index("ix_prompts_interviewee_id", "interview_prompts", ["interviewee_id"])


def downgrade() -> None:
    op.drop_index("ix_prompts_interviewee_id")
    op.drop_index("ix_prompts_position_id")
    op.drop_table("interview_prompts")
