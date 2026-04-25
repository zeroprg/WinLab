from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.config import settings
from server.models.assessment import Assessment
from server.models.assessment_criterion import AssessmentCriterion
from server.models.assessment_score import AssessmentScore
from server.models.interview_session import InterviewSession
from server.models.interviewee import Interviewee
from server.models.message import Message
from server.models.position import Position
from server.openai_client import chat_completion

logger = logging.getLogger("bkp-server.assessment")

ASSESSMENT_PROMPT_TEMPLATE = """\
You are an expert interview assessor. Analyze the following interview \
transcript and evaluate the candidate on the criteria listed below.

CANDIDATE: {candidate_name}
POSITION: {position_title}
SESSION DATE: {session_date}

CRITERIA (score each from 0 to 10):
{criteria_block}

TRANSCRIPT:
{transcript}

INSTRUCTIONS:
1. For each criterion, provide:
   - score: a number from 0 to 10 (one decimal place allowed)
   - justification: 1-2 sentences explaining the score
2. Provide an overall summary (3-5 sentences)
3. Respond in the same language as the interview transcript below.
4. Respond ONLY with valid JSON in this exact format:
{{
  "scores": [
    {{"criterion": "CriterionName", "score": 7.5, "justification": "..."}},
    ...
  ],
  "summary": "..."
}}
"""


async def assess_session(
    db: AsyncSession,
    session_id: str,
    model: Optional[str] = None,
) -> Assessment:
    """Run AI assessment on a completed interview session.

    Loads the full transcript, builds an assessment prompt,
    calls OpenAI Chat Completions, parses the structured response,
    and persists Assessment + AssessmentScore records.
    """
    interview_session = await db.scalar(
        select(InterviewSession).where(InterviewSession.id == session_id)
    )
    if not interview_session:
        raise ValueError(f"Session {session_id} not found")

    if interview_session.status not in ("completed", "in_progress"):
        raise ValueError(
            f"Session {session_id} has status '{interview_session.status}', "
            "expected 'completed' or 'in_progress'"
        )

    existing = await db.scalar(
        select(Assessment).where(Assessment.session_id == session_id)
    )
    if existing:
        raise ValueError(f"Session {session_id} already has an assessment")

    interviewee = await db.scalar(
        select(Interviewee).where(Interviewee.id == interview_session.interviewee_id)
    )
    candidate_name = "Unknown"
    position_title = "General"
    if interviewee:
        candidate_name = f"{interviewee.first_name} {interviewee.last_name}"
        if interviewee.position_id:
            position = await db.scalar(
                select(Position).where(Position.id == interviewee.position_id)
            )
            if position:
                position_title = position.title

    messages_rows = list(
        await db.scalars(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
        )
    )
    if not messages_rows:
        messages_rows = list(
            await db.scalars(
                select(Message)
                .where(Message.user_id == (interviewee.user_id if interviewee else ""))
                .order_by(Message.created_at.asc())
            )
        )

    user_messages = [m for m in messages_rows if m.role == "user"]
    if not user_messages:
        raise ValueError(
            f"No user messages in session {session_id} — skipping assessment"
        )

    transcript = "\n".join(
        f"[{m.role.upper()}]: {m.text}" for m in messages_rows
    )
    if not transcript.strip():
        raise ValueError(f"No transcript found for session {session_id}")

    pos_id = interviewee.position_id if interviewee else None
    criteria_rows = []
    if pos_id:
        criteria_rows = list(
            await db.scalars(
                select(AssessmentCriterion)
                .where(
                    AssessmentCriterion.position_id == pos_id,
                    AssessmentCriterion.is_active == True,
                )
                .order_by(AssessmentCriterion.display_order.asc())
            )
        )
    if not criteria_rows:
        criteria_rows = list(
            await db.scalars(
                select(AssessmentCriterion)
                .where(
                    AssessmentCriterion.position_id.is_(None),
                    AssessmentCriterion.is_active == True,
                )
                .order_by(AssessmentCriterion.display_order.asc())
            )
        )
    if not criteria_rows:
        raise ValueError("No assessment criteria configured")

    criteria_block = "\n".join(
        f"- {c.name} (weight: {c.weight}): {c.description or 'N/A'}"
        for c in criteria_rows
    )

    session_date = interview_session.started_at.strftime("%Y-%m-%d %H:%M UTC")

    assessment_prompt = ASSESSMENT_PROMPT_TEMPLATE.format(
        candidate_name=candidate_name,
        position_title=position_title,
        session_date=session_date,
        criteria_block=criteria_block,
        transcript=transcript,
    )

    raw_response = await chat_completion(
        messages=[],
        instructions=assessment_prompt,
        model=model or "gpt-4o",
    )

    parsed = _parse_assessment_response(raw_response, criteria_rows)

    now = datetime.now(timezone.utc)
    assessment = Assessment(
        id=str(uuid.uuid4()),
        session_id=session_id,
        assessor_type="ai_auto",
        total_score=parsed["total_score"],
        summary=parsed["summary"],
        raw_ai_response=raw_response,
        assessed_at=now,
        created_at=now,
    )
    db.add(assessment)

    criteria_by_name = {c.name.lower(): c for c in criteria_rows}
    for score_data in parsed["scores"]:
        criterion = criteria_by_name.get(score_data["criterion"].lower())
        if not criterion:
            continue
        score_record = AssessmentScore(
            id=str(uuid.uuid4()),
            assessment_id=assessment.id,
            criterion_id=criterion.id,
            score=score_data["score"],
            justification=score_data.get("justification", ""),
            created_at=now,
        )
        db.add(score_record)

    interview_session.status = "assessed"
    if interviewee:
        interviewee.status = "assessed"

    await db.commit()
    await db.refresh(assessment)

    logger.info(
        f"Assessment created for session {session_id}: "
        f"total_score={assessment.total_score:.1f}"
    )
    return assessment


def _parse_assessment_response(
    raw: str,
    criteria: List[AssessmentCriterion],
) -> Dict[str, Any]:
    """Parse AI response JSON and calculate weighted total score."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error(f"Failed to parse assessment JSON: {exc}")
        return {
            "scores": [],
            "summary": f"Failed to parse AI response: {exc}",
            "total_score": 0.0,
        }

    scores = data.get("scores", [])
    summary = data.get("summary", "")

    criteria_weights = {c.name.lower(): c.weight for c in criteria}

    total_weighted = 0.0
    total_weight = 0.0
    for s in scores:
        name = s.get("criterion", "").lower()
        score_val = float(s.get("score", 0))
        score_val = max(0.0, min(10.0, score_val))
        s["score"] = score_val
        weight = criteria_weights.get(name, 1.0)
        total_weighted += score_val * weight
        total_weight += weight

    total_score = round(total_weighted / total_weight, 1) if total_weight > 0 else 0.0

    return {
        "scores": scores,
        "summary": summary,
        "total_score": total_score,
    }
