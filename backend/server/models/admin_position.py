from __future__ import annotations

from sqlalchemy import Column, ForeignKey, String, Table

from server.models.base import Base

admin_positions = Table(
    "admin_positions",
    Base.metadata,
    Column(
        "user_id",
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "position_id",
        String(64),
        ForeignKey("positions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)
