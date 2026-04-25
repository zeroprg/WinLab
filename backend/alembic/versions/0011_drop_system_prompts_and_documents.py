"""Drop unused system_prompts and documents tables"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS system_prompts")
    op.execute("DROP TABLE IF EXISTS documents")


def downgrade() -> None:
    pass
