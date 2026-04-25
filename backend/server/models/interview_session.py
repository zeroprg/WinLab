from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from server.models.base import Base


class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(String(64), primary_key=True)
    interviewee_id = Column(
        String(64),
        ForeignKey("interviewees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_type = Column(String(32), nullable=False)  # 'voice' or 'text'
    status = Column(String(32), nullable=False, default="in_progress")
    started_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    ended_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    prompt_used = Column(Text, nullable=True)
    invite_token = Column(String(64), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    interviewee = relationship("Interviewee", back_populates="sessions")
    messages = relationship("Message", back_populates="session")
    assessment = relationship("Assessment", back_populates="session", uselist=False)
