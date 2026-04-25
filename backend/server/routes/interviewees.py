from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.db import get_db
from server.models.interview_prompt import InterviewPrompt
from server.models.interview_session import InterviewSession
from server.models.interviewee import Interviewee
from server.models.user import User
from server.middleware.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/interviewees", tags=["interviewees"], dependencies=[Depends(require_admin)])


async def _active_interviewee_prompt_text(
    db: AsyncSession, interviewee_id: str
) -> Optional[str]:
    row = await db.scalar(
        select(InterviewPrompt)
        .where(
            InterviewPrompt.interviewee_id == interviewee_id,
            InterviewPrompt.is_active == True,
        )
        .order_by(InterviewPrompt.version.desc())
        .limit(1)
    )
    return row.instructions if row else None


async def _upsert_interviewee_prompt(
    db: AsyncSession, interviewee: Interviewee, text: Any
) -> None:
    now = datetime.now(timezone.utc)
    normalized = (str(text).strip() if text is not None else "")

    existing_active = await db.scalar(
        select(InterviewPrompt)
        .where(
            InterviewPrompt.interviewee_id == interviewee.id,
            InterviewPrompt.is_active == True,
        )
        .order_by(InterviewPrompt.version.desc())
        .limit(1)
    )

    if not normalized:
        if existing_active:
            existing_active.is_active = False
            existing_active.updated_at = now
        return

    if existing_active and existing_active.instructions.strip() == normalized:
        return

    if existing_active:
        existing_active.is_active = False
        existing_active.updated_at = now

    max_v = await db.scalar(
        select(func.coalesce(func.max(InterviewPrompt.version), 0)).where(
            InterviewPrompt.interviewee_id == interviewee.id,
        )
    )
    next_v = int(max_v or 0) + 1
    db.add(
        InterviewPrompt(
            id=str(uuid.uuid4()),
            position_id=interviewee.position_id,
            interviewee_id=interviewee.id,
            instructions=normalized,
            version=next_v,
            is_active=True,
            created_at=now,
        )
    )


def _interviewee_to_dict(i: Interviewee) -> Dict[str, Any]:
    return {
        "id": i.id,
        "user_id": i.user_id,
        "position_id": i.position_id,
        "first_name": i.first_name,
        "last_name": i.last_name,
        "email": i.email,
        "phone": i.phone,
        "status": i.status,
        "source": i.source,
        "created_at": i.created_at.isoformat() if i.created_at else None,
        "updated_at": i.updated_at.isoformat() if i.updated_at else None,
    }


async def _interviewee_detail_dict(db: AsyncSession, interviewee: Interviewee) -> Dict[str, Any]:
    d = _interviewee_to_dict(interviewee)
    d["custom_prompt"] = await _active_interviewee_prompt_text(db, interviewee.id)
    sessions = list(
        await db.scalars(
            select(InterviewSession)
            .where(InterviewSession.interviewee_id == interviewee.id)
            .order_by(InterviewSession.started_at.desc())
        )
    )
    d["sessions"] = [
        {
            "id": s.id,
            "session_type": s.session_type,
            "status": s.status,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            "duration_seconds": s.duration_seconds,
        }
        for s in sessions
    ]
    return d


@router.get("")
async def list_interviewees(
    position_id: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    stmt = select(Interviewee).order_by(Interviewee.created_at.desc())
    if position_id:
        stmt = stmt.where(Interviewee.position_id == position_id)
    if status:
        stmt = stmt.where(Interviewee.status == status)

    if current_user.role != "superadmin":
        assigned_ids = [p.id for p in current_user.assigned_positions]
        if assigned_ids:
            stmt = stmt.where(Interviewee.position_id.in_(assigned_ids))
        else:
            return []

    rows = list(await db.scalars(stmt))
    return [_interviewee_to_dict(i) for i in rows]


@router.get("/{interviewee_id}")
async def get_interviewee(
    interviewee_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    interviewee = await db.scalar(
        select(Interviewee).where(Interviewee.id == interviewee_id)
    )
    if not interviewee:
        raise HTTPException(status_code=404, detail="Interviewee not found")
    return await _interviewee_detail_dict(db, interviewee)


@router.post("", status_code=201)
async def create_interviewee(
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    email = (payload.get("email") or "").strip().lower()
    first_name = (payload.get("first_name") or "").strip()
    last_name = (payload.get("last_name") or "").strip()

    if not email or not first_name or not last_name:
        raise HTTPException(
            status_code=400,
            detail="email, first_name, and last_name are required",
        )

    existing = await db.scalar(
        select(Interviewee).where(Interviewee.email == email)
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Interviewee with email '{email}' already exists",
        )

    now = datetime.now(timezone.utc)

    user = await db.scalar(select(User).where(User.id == email))
    if not user:
        user = User(
            id=email,
            display_name=f"{first_name} {last_name}",
            created_at=now,
        )
        db.add(user)

    interviewee = Interviewee(
        id=str(uuid.uuid4()),
        user_id=email,
        position_id=payload.get("position_id"),
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=(payload.get("phone") or "").strip() or None,
        status="pending",
        source=payload.get("source"),
        created_at=now,
    )
    db.add(interviewee)

    prompt_text = (payload.get("custom_prompt") or "").strip()
    if prompt_text:
        prompt = InterviewPrompt(
            id=str(uuid.uuid4()),
            position_id=interviewee.position_id,
            interviewee_id=interviewee.id,
            instructions=prompt_text,
            version=1,
            is_active=True,
            created_at=now,
        )
        db.add(prompt)

    await db.commit()
    await db.refresh(interviewee)
    return await _interviewee_detail_dict(db, interviewee)


@router.delete("/{interviewee_id}", status_code=204)
async def delete_interviewee(
    interviewee_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    interviewee = await db.scalar(
        select(Interviewee).where(Interviewee.id == interviewee_id)
    )
    if not interviewee:
        raise HTTPException(status_code=404, detail="Interviewee not found")

    session_count = await db.scalar(
        select(func.count()).select_from(InterviewSession).where(
            InterviewSession.interviewee_id == interviewee_id
        )
    )
    if session_count and session_count > 0:
        in_progress = await db.scalar(
            select(func.count()).select_from(InterviewSession).where(
                InterviewSession.interviewee_id == interviewee_id,
                InterviewSession.status == "in_progress",
            )
        )
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Candidate has sessions and cannot be deleted. Use archive instead.",
                "has_sessions": True,
                "in_progress": in_progress or 0,
            },
        )

    await db.delete(interviewee)
    await db.commit()


@router.patch("/{interviewee_id}")
async def update_interviewee(
    interviewee_id: str,
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    interviewee = await db.scalar(
        select(Interviewee).where(Interviewee.id == interviewee_id)
    )
    if not interviewee:
        raise HTTPException(status_code=404, detail="Interviewee not found")

    _required = {"first_name", "last_name"}
    for field in ("first_name", "last_name", "phone", "status", "position_id"):
        if field in payload:
            val = payload[field]
            if isinstance(val, str):
                val = val.strip()
                if not val and field in _required:
                    continue
                val = val or None
            setattr(interviewee, field, val)

    if "custom_prompt" in payload:
        await _upsert_interviewee_prompt(db, interviewee, payload.get("custom_prompt"))

    interviewee.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(interviewee)
    return await _interviewee_detail_dict(db, interviewee)
