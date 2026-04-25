from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from server.models.base import Base


class InviteLink(Base):
    __tablename__ = "invite_links"

    id = Column(String(64), primary_key=True)
    token = Column(String(32), unique=True, nullable=False, index=True)
    position_id = Column(
        String(64),
        ForeignKey("positions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    candidate_email = Column(String(255), nullable=True)
    max_attempts = Column(Integer, nullable=False, default=1)
    used_attempts = Column(Integer, nullable=False, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    position = relationship("Position")
