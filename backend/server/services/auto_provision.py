"""Auto-create interviewee and interview_session records on demand.

Called from /api/message and /api/realtime/session so that the full
assessment chain (interviewee -> session -> assessment) works without
requiring manual setup via Excel import or admin API.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.models.interviewee import Interviewee
from server.models.interview_session import InterviewSession
from server.models.user import User

logger = logging.getLogger("bkp-server.auto_provision")


async def _ensure_user_record(db: AsyncSession, user_id: str) -> None:
    """Make sure a `users` row exists so the FK from `interviewees` is valid."""
    existing_user = await db.scalar(select(User).where(User.id == user_id))
    if existing_user:
        return
    db.add(User(id=user_id, created_at=datetime.now(timezone.utc)))
    await db.flush()


async def ensure_interviewee(
    db: AsyncSession,
    user_id: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> Interviewee:
    """Return existing interviewee or create one from the user_id (email).

    If *first_name* / *last_name* are given they are used when creating
    a new record and also update an existing record whose names were
    auto-derived from the email prefix.
    """
    await _ensure_user_record(db, user_id)
    existing = await db.scalar(
        select(Interviewee).where(Interviewee.user_id == user_id)
    )
    if existing:
        if first_name and first_name.strip():
            existing.first_name = first_name.strip()
        if last_name and last_name.strip():
            existing.last_name = last_name.strip()
        return existing

    email = user_id
    if not first_name or not first_name.strip():
        parts = email.split("@")[0].split(".") if "@" in email else [email]
        first_name = parts[0].capitalize() if parts else email
    else:
        first_name = first_name.strip()
    if not last_name or not last_name.strip():
        parts = email.split("@")[0].split(".") if "@" in email else [email]
        last_name = parts[1].capitalize() if len(parts) > 1 else ""
    else:
        last_name = last_name.strip()

    interviewee = Interviewee(
        id=str(uuid.uuid4()),
        user_id=user_id,
        first_name=first_name,
        last_name=last_name,
        email=email,
        status="pending",
        created_at=datetime.now(timezone.utc),
    )
    db.add(interviewee)
    await db.flush()
    logger.info(f"Auto-created interviewee {interviewee.id} for user {user_id}")
    return interviewee


async def ensure_interview_session(
    db: AsyncSession,
    interviewee: Interviewee,
    session_type: str = "text",
    prompt_used: Optional[str] = None,
) -> InterviewSession:
    """Return an active session or create a new one."""
    active = await db.scalar(
        select(InterviewSession).where(
            InterviewSession.interviewee_id == interviewee.id,
            InterviewSession.status == "in_progress",
        )
    )
    if active:
        return active

    now = datetime.now(timezone.utc)
    session = InterviewSession(
        id=str(uuid.uuid4()),
        interviewee_id=interviewee.id,
        session_type=session_type,
        status="in_progress",
        started_at=now,
        prompt_used=prompt_used,
        created_at=now,
    )
    db.add(session)
    await db.flush()
    logger.info(
        f"Auto-created interview session {session.id} "
        f"(type={session_type}) for interviewee {interviewee.id}"
    )
    return session
