from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from server.models.base import Base


class InterviewPrompt(Base):
    __tablename__ = "interview_prompts"
    __table_args__ = (
        CheckConstraint(
            "position_id IS NOT NULL OR interviewee_id IS NOT NULL",
            name="ck_prompt_has_owner",
        ),
    )

    id = Column(String(64), primary_key=True)
    position_id = Column(
        String(64),
        ForeignKey("positions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    interviewee_id = Column(
        String(64),
        ForeignKey("interviewees.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    instructions = Column(Text, nullable=False)
    version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(DateTime(timezone=True), nullable=True)

    position = relationship("Position", back_populates="prompts")
    interviewee = relationship("Interviewee", back_populates="prompts")
