"""Onboarding domain models."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from server.models.base import Base


class OnboardingPlan(Base):
    __tablename__ = "onboarding_plans"

    id = Column(String(64), primary_key=True)
    employee_id = Column(String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False, default="Адаптация")
    stage = Column(String(32), nullable=False, default="day1")  # day1, week1, month1
    status = Column(String(32), nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=True)

    tasks = relationship("OnboardingTask", back_populates="plan", cascade="all, delete-orphan")


class OnboardingTask(Base):
    __tablename__ = "onboarding_tasks"

    id = Column(String(64), primary_key=True)
    plan_id = Column(String(64), ForeignKey("onboarding_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    owner_id = Column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    due_date = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, default="pending")  # pending, in_progress, done, overdue
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    plan = relationship("OnboardingPlan", back_populates="tasks")
