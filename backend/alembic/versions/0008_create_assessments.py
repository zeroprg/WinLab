"""Create assessments and assessment_scores tables"""

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assessments",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("session_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("assessor_type", sa.String(length=32), nullable=False, server_default="ai_auto"),
        sa.Column("total_score", sa.Float(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("raw_ai_response", sa.Text(), nullable=True),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["interview_sessions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_assessments_session_id", "assessments", ["session_id"])

    op.create_table(
        "assessment_scores",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("assessment_id", sa.String(length=64), nullable=False),
        sa.Column("criterion_id", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["criterion_id"], ["assessment_criteria.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("assessment_id", "criterion_id", name="uq_assessment_criterion"),
    )
    op.create_index("ix_scores_assessment_id", "assessment_scores", ["assessment_id"])
    op.create_index("ix_scores_criterion_id", "assessment_scores", ["criterion_id"])


def downgrade() -> None:
    op.drop_index("ix_scores_criterion_id")
    op.drop_index("ix_scores_assessment_id")
    op.drop_table("assessment_scores")
    op.drop_index("ix_assessments_session_id")
    op.drop_table("assessments")
