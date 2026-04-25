from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.db import get_db, make_session
from server.middleware.auth import get_current_user, require_admin
from server.models.assessment import Assessment
from server.models.assessment_criterion import AssessmentCriterion
from server.models.assessment_score import AssessmentScore
from server.models.interview_session import InterviewSession
from server.models.interviewee import Interviewee
from server.models.invite_link import InviteLink
from server.models.message import Message
from server.models.user import User
from server.services.assessment_service import assess_session

logger = logging.getLogger("bkp-server.routes.assessments")

router = APIRouter(prefix="/api", tags=["assessments"], dependencies=[Depends(require_admin)])
public_router = APIRouter(prefix="/api", tags=["assessments-public"])


@router.post("/assess/{session_id}")
async def trigger_assessment(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Trigger AI assessment for a completed interview session."""
    try:
        assessment = await assess_session(db, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"Assessment failed for session {session_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Assessment failed: {exc}")

    return await _assessment_to_dict(db, assessment)


@router.get("/assessments/{session_id}")
async def get_assessment(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Get assessment results for a session."""
    assessment = await db.scalar(
        select(Assessment).where(Assessment.session_id == session_id)
    )
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found for this session")

    return await _assessment_to_dict(db, assessment)


@router.get("/criteria")
async def list_criteria(
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """List all assessment criteria."""
    rows = list(
        await db.scalars(
            select(AssessmentCriterion)
            .where(AssessmentCriterion.is_active == True)
            .order_by(AssessmentCriterion.display_order)
        )
    )
    return [
        {
            "id": c.id,
            "name": c.name,
            "description": c.description,
            "max_score": c.max_score,
            "weight": c.weight,
            "display_order": c.display_order,
        }
        for c in rows
    ]


@router.get("/sessions")
async def list_sessions(
    interviewee_id: Optional[str] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List interview sessions with optional filters."""
    stmt = select(InterviewSession).where(
        InterviewSession.status != "abandoned"
    ).order_by(InterviewSession.started_at.desc())
    if interviewee_id:
        stmt = stmt.where(InterviewSession.interviewee_id == interviewee_id)
    if status:
        stmt = stmt.where(InterviewSession.status == status)

    if current_user.role != "superadmin":
        assigned_ids = [p.id for p in current_user.assigned_positions]
        if assigned_ids:
            stmt = stmt.join(
                Interviewee, InterviewSession.interviewee_id == Interviewee.id
            ).where(Interviewee.position_id.in_(assigned_ids))
        else:
            return []

    from server.models.message import Message

    rows = list(await db.scalars(stmt))
    session_ids = [s.id for s in rows]

    msg_counts: Dict[str, int] = {}
    if session_ids:
        cnt_rows = await db.execute(
            select(Message.session_id, func.count())
            .where(Message.session_id.in_(session_ids))
            .group_by(Message.session_id)
        )
        msg_counts = dict(cnt_rows.all())

    return [
        {
            "id": s.id,
            "interviewee_id": s.interviewee_id,
            "session_type": s.session_type,
            "status": s.status,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            "duration_seconds": s.duration_seconds,
            "message_count": msg_counts.get(s.id, 0),
        }
        for s in rows
    ]


async def _assessment_to_dict(db: AsyncSession, a: Assessment) -> Dict[str, Any]:
    scores = list(
        await db.scalars(
            select(AssessmentScore).where(AssessmentScore.assessment_id == a.id)
        )
    )
    criteria_ids = [s.criterion_id for s in scores]
    criteria_map = {}
    if criteria_ids:
        criteria_rows = list(
            await db.scalars(
                select(AssessmentCriterion).where(
                    AssessmentCriterion.id.in_(criteria_ids)
                )
            )
        )
        criteria_map = {c.id: c for c in criteria_rows}

    return {
        "id": a.id,
        "session_id": a.session_id,
        "assessor_type": a.assessor_type,
        "total_score": a.total_score,
        "summary": a.summary,
        "assessed_at": a.assessed_at.isoformat() if a.assessed_at else None,
        "scores": [
            {
                "criterion": criteria_map.get(s.criterion_id, None)
                and criteria_map[s.criterion_id].name
                or s.criterion_id,
                "score": s.score,
                "justification": s.justification,
            }
            for s in scores
        ],
    }


async def _bg_assess(session_id: str) -> None:
    """Run assessment in a background task with its own DB session."""
    async with make_session() as db:
        try:
            await assess_session(db, session_id)
        except Exception as exc:
            logger.warning("Background assessment failed for %s: %s", session_id, exc)


@public_router.post("/sessions/{session_id}/complete")
async def complete_session(
    session_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Public endpoint for candidates to end their interview and trigger assessment."""
    session = await db.scalar(
        select(InterviewSession).where(InterviewSession.id == session_id)
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status not in ("in_progress",):
        return {"status": session.status}

    user_msgs = list(
        await db.scalars(
            select(Message).where(
                Message.session_id == session_id,
                Message.role == "user",
            )
        )
    )
    has_messages = len(user_msgs) > 0

    now = datetime.now(timezone.utc)
    if has_messages:
        session.status = "completed"
    else:
        session.status = "abandoned"
        if session.invite_token:
            link = await db.scalar(
                select(InviteLink).where(InviteLink.token == session.invite_token)
            )
            if link and link.used_attempts > 0:
                link.used_attempts -= 1
                if link.status == "exhausted" and link.used_attempts < link.max_attempts:
                    link.status = "active"

    session.ended_at = now
    if session.started_at:
        session.duration_seconds = int(
            (now - session.started_at).total_seconds()
        )
    await db.commit()

    if has_messages:
        background_tasks.add_task(_bg_assess, session_id)

    return {"status": session.status}
