from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from server.models.base import Base


class Interviewee(Base):
    __tablename__ = "interviewees"

    id = Column(String(64), primary_key=True)
    user_id = Column(
        String(64),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    position_id = Column(
        String(64),
        ForeignKey("positions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    first_name = Column(String(128), nullable=False)
    last_name = Column(String(128), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    phone = Column(String(64), nullable=True)
    status = Column(String(32), nullable=False, default="pending")
    source = Column(String(128), nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", backref="interviewee_profile")
    position = relationship("Position", back_populates="interviewees")
    sessions = relationship("InterviewSession", back_populates="interviewee")
    prompts = relationship(
        "InterviewPrompt",
        back_populates="interviewee",
        foreign_keys="InterviewPrompt.interviewee_id",
    )
