"""Seed default assessment criteria"""

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

CRITERIA = [
    {
        "name": "Solutions",
        "description": "Ability to propose solutions and handle objections",
        "weight": 1.0,
        "display_order": 1,
    },
    {
        "name": "Empathy",
        "description": "Emotional intelligence and rapport building",
        "weight": 1.0,
        "display_order": 2,
    },
    {
        "name": "Information",
        "description": "Clarity, completeness, and accuracy of information provided",
        "weight": 1.0,
        "display_order": 3,
    },
    {
        "name": "Communication",
        "description": "Speaking skills, professionalism, language quality",
        "weight": 1.0,
        "display_order": 4,
    },
    {
        "name": "Experience Relevance",
        "description": "How relevant their prior experience is to the position",
        "weight": 0.8,
        "display_order": 5,
    },
]


def upgrade() -> None:
    criteria_table = sa.table(
        "assessment_criteria",
        sa.column("id", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("max_score", sa.Float),
        sa.column("weight", sa.Float),
        sa.column("is_active", sa.Boolean),
        sa.column("display_order", sa.Integer),
        sa.column("created_at", sa.DateTime),
    )
    now = datetime.now(timezone.utc)
    rows = []
    for c in CRITERIA:
        rows.append({
            "id": str(uuid.uuid4()),
            "name": c["name"],
            "description": c["description"],
            "max_score": 10.0,
            "weight": c["weight"],
            "is_active": True,
            "display_order": c["display_order"],
            "created_at": now,
        })
    op.bulk_insert(criteria_table, rows)


def downgrade() -> None:
    names = [c["name"] for c in CRITERIA]
    op.execute(
        sa.text("DELETE FROM assessment_criteria WHERE name IN :names").bindparams(
            sa.bindparam("names", expanding=True)
        ),
        {"names": names},
    )
