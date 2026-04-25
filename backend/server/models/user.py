from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.orm import relationship

from server.models.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True)
    display_name = Column(String(128), nullable=True)
    role = Column(String(32), nullable=False, default="candidate")
    password_hash = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    assigned_positions = relationship(
        "Position",
        secondary="admin_positions",
        back_populates="assigned_admins",
        lazy="selectin",
    )
