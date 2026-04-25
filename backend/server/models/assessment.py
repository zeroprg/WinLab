from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from server.models.base import Base


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(String(64), primary_key=True)
    session_id = Column(
        String(64),
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    assessor_type = Column(String(32), nullable=False, default="ai_auto")
    total_score = Column(Float, nullable=True)
    summary = Column(Text, nullable=True)
    raw_ai_response = Column(Text, nullable=True)
    assessed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    session = relationship("InterviewSession", back_populates="assessment")
    scores = relationship("AssessmentScore", back_populates="assessment", cascade="all, delete-orphan")
