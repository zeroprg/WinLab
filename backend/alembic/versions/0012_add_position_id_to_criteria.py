"""Add position_id to assessment_criteria for per-position criteria"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    naming = {
        "uq": "uq_%(table_name)s_%(column_0_name)s",
    }
    with op.batch_alter_table(
        "assessment_criteria",
        naming_convention=naming,
    ) as batch_op:
        batch_op.add_column(sa.Column("position_id", sa.String(64), nullable=True))
        batch_op.create_foreign_key(
            "fk_criteria_position",
            "positions",
            ["position_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index("ix_criteria_position_id", ["position_id"])
        batch_op.drop_constraint("uq_assessment_criteria_name", type_="unique")


def downgrade() -> None:
    with op.batch_alter_table("assessment_criteria") as batch_op:
        batch_op.create_unique_constraint("uq_assessment_criteria_name", ["name"])
        batch_op.drop_index("ix_criteria_position_id")
        batch_op.drop_constraint("fk_criteria_position", type_="foreignkey")
        batch_op.drop_column("position_id")
