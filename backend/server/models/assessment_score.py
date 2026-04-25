from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from server.models.base import Base


class AssessmentScore(Base):
    __tablename__ = "assessment_scores"
    __table_args__ = (
        UniqueConstraint("assessment_id", "criterion_id", name="uq_assessment_criterion"),
    )

    id = Column(String(64), primary_key=True)
    assessment_id = Column(
        String(64),
        ForeignKey("assessments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    criterion_id = Column(
        String(64),
        ForeignKey("assessment_criteria.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    score = Column(Float, nullable=False)
    justification = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    assessment = relationship("Assessment", back_populates="scores")
    criterion = relationship("AssessmentCriterion")
