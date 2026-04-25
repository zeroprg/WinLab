"""Add role, password_hash, is_active to users; seed initial superadmin"""

import os
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("role", sa.String(32), nullable=False, server_default="candidate")
        )
        batch_op.add_column(
            sa.Column("password_hash", sa.String(255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1"))
        )

    _seed_superadmin()


def _seed_superadmin() -> None:
    email = os.environ.get("SUPERADMIN_EMAIL", "").strip()
    password = os.environ.get("SUPERADMIN_PASSWORD", "").strip()

    if not email or not password:
        try:
            from server.config import settings
            email = email or settings.SUPERADMIN_EMAIL
            password = password or settings.SUPERADMIN_PASSWORD
        except Exception:
            pass

    if not email or not password:
        print(
            "[migration-0014] SUPERADMIN_EMAIL / SUPERADMIN_PASSWORD not set — "
            "skipping superadmin seed. Create one manually via API later."
        )
        return

    import bcrypt

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    now = datetime.now(timezone.utc)

    users = sa.table(
        "users",
        sa.column("id", sa.String),
        sa.column("display_name", sa.String),
        sa.column("role", sa.String),
        sa.column("password_hash", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime),
    )

    conn = op.get_bind()
    existing = conn.execute(
        sa.text("SELECT id FROM users WHERE id = :email"),
        {"email": email.lower()},
    ).fetchone()

    if existing:
        conn.execute(
            sa.text(
                "UPDATE users SET role = :role, password_hash = :pw WHERE id = :email"
            ),
            {"role": "superadmin", "pw": hashed, "email": email.lower()},
        )
        print(f"[migration-0014] Updated existing user {email} to superadmin.")
    else:
        op.bulk_insert(users, [{
            "id": email.lower(),
            "display_name": email,
            "role": "superadmin",
            "password_hash": hashed,
            "is_active": True,
            "created_at": now,
        }])
        print(f"[migration-0014] Created superadmin: {email}")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("is_active")
        batch_op.drop_column("password_hash")
        batch_op.drop_column("role")
