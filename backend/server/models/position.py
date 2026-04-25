from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import relationship

from server.models.base import Base


class Position(Base):
    __tablename__ = "positions"

    id = Column(String(64), primary_key=True)
    title = Column(String(255), nullable=False, unique=True)
    department = Column(String(128), nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    time_limit_minutes = Column(Float, nullable=True)
    locale = Column(String(8), nullable=True, default="ru")
    interview_mode = Column(String(16), nullable=False, default="both")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(DateTime(timezone=True), nullable=True)

    interviewees = relationship("Interviewee", back_populates="position")
    prompts = relationship(
        "InterviewPrompt",
        back_populates="position",
        foreign_keys="InterviewPrompt.position_id",
    )
    assigned_admins = relationship(
        "User",
        secondary="admin_positions",
        back_populates="assigned_positions",
        lazy="selectin",
    )
