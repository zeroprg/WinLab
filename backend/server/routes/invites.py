from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.db import get_db
from server.middleware.auth import require_admin
from server.models.invite_link import InviteLink
from server.models.position import Position

logger = logging.getLogger("bkp-server.routes.invites")

router = APIRouter(prefix="/api/invites", tags=["invites"])


def _generate_token(length: int = 12) -> str:
    return secrets.token_urlsafe(length)[:length]


def _link_to_dict(link: InviteLink) -> Dict[str, Any]:
    return {
        "id": link.id,
        "token": link.token,
        "position_id": link.position_id,
        "candidate_email": link.candidate_email,
        "max_attempts": link.max_attempts,
        "used_attempts": link.used_attempts,
        "expires_at": link.expires_at.isoformat() if link.expires_at else None,
        "created_by": link.created_by,
        "status": link.status,
        "created_at": link.created_at.isoformat() if link.created_at else None,
    }


@router.post("", status_code=201, dependencies=[Depends(require_admin)])
async def create_invite(
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    position_id = (payload.get("position_id") or "").strip()
    if not position_id:
        raise HTTPException(status_code=400, detail="position_id is required")

    position = await db.scalar(select(Position).where(Position.id == position_id))
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    now = datetime.now(timezone.utc)
    token = _generate_token()

    link = InviteLink(
        id=str(uuid.uuid4()),
        token=token,
        position_id=position_id,
        candidate_email=(payload.get("candidate_email") or "").strip() or None,
        max_attempts=int(payload.get("max_attempts", 1)),
        created_by=(payload.get("created_by") or "").strip() or None,
        status="active",
        created_at=now,
    )

    expires = payload.get("expires_at")
    if expires:
        link.expires_at = datetime.fromisoformat(str(expires))

    db.add(link)
    await db.commit()
    await db.refresh(link)
    return _link_to_dict(link)


@router.get("", dependencies=[Depends(require_admin)])
async def list_invites(
    position_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    stmt = select(InviteLink).order_by(InviteLink.created_at.desc())
    if position_id:
        stmt = stmt.where(InviteLink.position_id == position_id)
    rows = list(await db.scalars(stmt))
    return [_link_to_dict(r) for r in rows]


@router.get("/{token}/validate")
async def validate_invite(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Public endpoint — validate a token and return position info."""
    link = await db.scalar(select(InviteLink).where(InviteLink.token == token))
    if not link:
        raise HTTPException(status_code=404, detail="Invalid invite link")

    if link.status == "revoked":
        raise HTTPException(status_code=410, detail="This invite has been revoked")

    if link.used_attempts >= link.max_attempts:
        raise HTTPException(
            status_code=410,
            detail="All attempts have been used. Contact your recruiter for a new link.",
        )

    if link.expires_at and datetime.now(timezone.utc) > link.expires_at:
        raise HTTPException(status_code=410, detail="This invite link has expired")

    position = await db.scalar(select(Position).where(Position.id == link.position_id))

    return {
        "token": link.token,
        "position_id": link.position_id,
        "position_title": position.title if position else "Unknown",
        "candidate_email": link.candidate_email,
        "attempts_remaining": link.max_attempts - link.used_attempts,
        "time_limit_minutes": position.time_limit_minutes if position else None,
        "locale": (position.locale if position else None) or "ru",
        "interview_mode": (position.interview_mode if position else None) or "both",
    }


@router.post("/{token}/consume")
async def consume_invite(
    token: str,
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Called when a candidate starts an interview via invite link.

    Increments used_attempts, auto-provisions interviewee+session,
    and returns session info.
    """
    from server.services.auto_provision import ensure_interviewee, ensure_interview_session
    from server.services.prompt_resolver import resolve_prompt

    link = await db.scalar(select(InviteLink).where(InviteLink.token == token))
    if not link:
        raise HTTPException(status_code=404, detail="Invalid invite link")

    if link.status == "revoked":
        raise HTTPException(status_code=410, detail="Invite revoked")

    if link.used_attempts >= link.max_attempts:
        raise HTTPException(status_code=410, detail="No attempts remaining")

    if link.expires_at and datetime.now(timezone.utc) > link.expires_at:
        raise HTTPException(status_code=410, detail="Invite expired")

    email = (payload.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="email is required")

    if link.candidate_email and email != link.candidate_email.lower():
        raise HTTPException(
            status_code=403,
            detail="This invite is assigned to a different email address",
        )

    from server.models.interview_session import InterviewSession

    try:
        fname = (payload.get("first_name") or "").strip() or None
        lname = (payload.get("last_name") or "").strip() or None
        interviewee = await ensure_interviewee(
            db, user_id=email, first_name=fname, last_name=lname,
        )

        # Block if candidate has an active interview for a DIFFERENT position
        active_sessions = list(
            await db.scalars(
                select(InterviewSession).where(
                    InterviewSession.interviewee_id == interviewee.id,
                    InterviewSession.status == "in_progress",
                )
            )
        )
        for s in active_sessions:
            other_position_id: str | None = None
            if s.invite_token and s.invite_token != token:
                other_link = await db.scalar(
                    select(InviteLink).where(InviteLink.token == s.invite_token)
                )
                if other_link:
                    other_position_id = other_link.position_id
            elif not s.invite_token and interviewee.position_id and interviewee.position_id != link.position_id:
                other_position_id = interviewee.position_id

            if other_position_id and other_position_id != link.position_id:
                other_pos = await db.scalar(
                    select(Position).where(Position.id == other_position_id)
                )
                other_title = other_pos.title if other_pos else "—"
                this_pos = await db.scalar(
                    select(Position).where(Position.id == link.position_id)
                )
                this_locale = (this_pos.locale if this_pos else None) or "ru"
                if this_locale == "en":
                    msg = (
                        f"You are currently in an active interview for \"{other_title}\". "
                        f"Please complete or end that interview before starting a new one."
                    )
                else:
                    msg = (
                        f"У вас уже идёт интервью на вакансию «{other_title}». "
                        f"Пожалуйста, завершите его, прежде чем начинать новое."
                    )
                raise HTTPException(status_code=409, detail=msg)

        interviewee.position_id = link.position_id

        # Complete any stale in-progress sessions for the SAME position
        now = datetime.now(timezone.utc)
        for s in active_sessions:
            s.status = "completed"
            s.ended_at = now

        locale = (payload.get("locale") or "").strip() or None
        instructions = await resolve_prompt(db, user_id=email, locale=locale)

        session = InterviewSession(
            id=str(uuid.uuid4()),
            interviewee_id=interviewee.id,
            session_type="text",
            status="in_progress",
            started_at=now,
            prompt_used=instructions,
            invite_token=token,
            created_at=now,
        )
        db.add(session)

        link.used_attempts += 1
        if link.used_attempts >= link.max_attempts:
            link.status = "exhausted"

        await db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("consume_invite failed for token=%s email=%s", token, email)
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Internal server error while starting interview",
        ) from exc

    return {
        "session_id": session.id,
        "interviewee_id": interviewee.id,
        "position_id": link.position_id,
        "attempts_remaining": link.max_attempts - link.used_attempts,
        "instructions": instructions,
    }


@router.patch("/{token}", dependencies=[Depends(require_admin)])
async def update_invite(
    token: str,
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    link = await db.scalar(select(InviteLink).where(InviteLink.token == token))
    if not link:
        raise HTTPException(status_code=404, detail="Invite not found")

    if "status" in payload:
        link.status = payload["status"]

    if "max_attempts" in payload:
        new_max = int(payload["max_attempts"])
        if new_max < link.used_attempts:
            raise HTTPException(
                status_code=400,
                detail="max_attempts cannot be less than used_attempts",
            )
        link.max_attempts = new_max
        if link.status == "exhausted" and link.used_attempts < new_max:
            link.status = "active"

    await db.commit()
    await db.refresh(link)
    return _link_to_dict(link)
