from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.db import get_db
from server.middleware.auth import get_current_user, require_admin
from server.models.admin_position import admin_positions
from server.models.assessment_criterion import AssessmentCriterion
from server.models.interview_prompt import InterviewPrompt
from server.models.position import Position
from server.models.user import User

logger = logging.getLogger("bkp-server.routes.positions")

router = APIRouter(prefix="/api/positions", tags=["positions"], dependencies=[Depends(require_admin)])

_META_PROMPT = """\
You are an expert HR consultant and interview designer.

Given a job title (and optionally a department or short description), generate a \
complete, structured interview prompt that an AI voice/chat interviewer will use \
to conduct a screening interview with a candidate.

The generated prompt MUST follow this exact structure:

1. ROLE — one sentence defining who the AI is and what position it is interviewing for.
2. OPENING — the exact greeting and first question the AI must say immediately when the call starts. Include the job title in the greeting.
3. STEPS — 5-7 numbered interview steps (STEP 1, STEP 2, …). Each step must contain:
   - A topic (e.g. Experience, Education, Motivation, Technical skills, Situational question, Roleplay, Closing).
   - The exact question or instruction for the AI.
   - A follow-up instruction if the answer is too short.
   Adapt topics to the specific role (e.g. for a developer: coding experience, tech stack; for a nurse: certifications, patient care scenarios).
4. CLOSING — the exact farewell phrase and instruction to stop responding.
5. RULES — bullet-pointed behavioural rules (stay professional, don't skip steps, ask follow-ups, do not reveal scoring, internally rate answers 1-5, etc.).

Output ONLY the interview prompt text, ready to be used as-is. Do NOT add meta-commentary, markdown formatting, or explanations.\
"""


async def _active_position_prompt_text(db: AsyncSession, position_id: str) -> Optional[str]:
    row = await db.scalar(
        select(InterviewPrompt)
        .where(
            InterviewPrompt.position_id == position_id,
            InterviewPrompt.interviewee_id.is_(None),
            InterviewPrompt.is_active == True,
        )
        .order_by(InterviewPrompt.version.desc())
        .limit(1)
    )
    return row.instructions if row else None


async def _position_prompts_bulk(db: AsyncSession, position_ids: List[str]) -> Dict[str, Optional[str]]:
    if not position_ids:
        return {}
    rows = list(
        await db.scalars(
            select(InterviewPrompt).where(
                InterviewPrompt.position_id.in_(position_ids),
                InterviewPrompt.interviewee_id.is_(None),
                InterviewPrompt.is_active == True,
            )
        )
    )
    best: Dict[str, InterviewPrompt] = {}
    for r in rows:
        cur = best.get(r.position_id)
        if cur is None or r.version > cur.version:
            best[r.position_id] = r
    return {pid: (best[pid].instructions if pid in best else None) for pid in position_ids}


async def _upsert_position_prompt(db: AsyncSession, position_id: str, text: Any) -> None:
    """Deactivate previous active position-level prompt; add new row or clear only."""
    now = datetime.now(timezone.utc)
    normalized = (str(text).strip() if text is not None else "")

    existing_active = await db.scalar(
        select(InterviewPrompt)
        .where(
            InterviewPrompt.position_id == position_id,
            InterviewPrompt.interviewee_id.is_(None),
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
            InterviewPrompt.position_id == position_id,
            InterviewPrompt.interviewee_id.is_(None),
        )
    )
    next_v = int(max_v or 0) + 1
    db.add(
        InterviewPrompt(
            id=str(uuid.uuid4()),
            position_id=position_id,
            interviewee_id=None,
            instructions=normalized,
            version=next_v,
            is_active=True,
            created_at=now,
        )
    )


async def _position_to_api_dict(db: AsyncSession, p: Position) -> Dict[str, Any]:
    d = {
        "id": p.id,
        "title": p.title,
        "department": p.department,
        "description": p.description,
        "is_active": p.is_active,
        "time_limit_minutes": p.time_limit_minutes,
        "locale": p.locale or "ru",
        "interview_mode": p.interview_mode or "both",
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }
    d["prompt"] = await _active_position_prompt_text(db, p.id)
    return d


@router.get("")
async def list_positions(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    stmt = select(Position).order_by(Position.title)
    if active_only:
        stmt = stmt.where(Position.is_active == True)

    if current_user.role != "superadmin":
        assigned_ids = [p.id for p in current_user.assigned_positions]
        if assigned_ids:
            stmt = stmt.where(Position.id.in_(assigned_ids))
        else:
            return []

    from server.models.interviewee import Interviewee

    rows = list(await db.scalars(stmt))
    ids = [p.id for p in rows]
    prompts = await _position_prompts_bulk(db, ids)

    counts_rows = await db.execute(
        select(Interviewee.position_id, func.count())
        .where(Interviewee.position_id.in_(ids))
        .group_by(Interviewee.position_id)
    )
    candidate_counts: Dict[str, int] = dict(counts_rows.all())

    return [
        {
            "id": p.id,
            "title": p.title,
            "department": p.department,
            "description": p.description,
            "is_active": p.is_active,
            "time_limit_minutes": p.time_limit_minutes,
            "locale": p.locale or "ru",
            "interview_mode": p.interview_mode or "both",
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "updated_at": p.updated_at.isoformat() if p.updated_at else None,
            "prompt": prompts.get(p.id),
            "candidate_count": candidate_counts.get(p.id, 0),
        }
        for p in rows
    ]


@router.post("", status_code=201)
async def create_position(
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")

    existing = await db.scalar(select(Position).where(Position.title == title))
    if existing:
        raise HTTPException(status_code=409, detail=f"Position '{title}' already exists")

    now = datetime.now(timezone.utc)
    tlm = payload.get("time_limit_minutes")
    locale_val = (payload.get("locale") or "").strip() or "ru"
    mode_val = (payload.get("interview_mode") or "").strip() or "both"
    if mode_val not in ("text", "voice", "both"):
        mode_val = "both"
    position = Position(
        id=str(uuid.uuid4()),
        title=title,
        department=(payload.get("department") or "").strip() or None,
        description=(payload.get("description") or "").strip() or None,
        is_active=payload.get("is_active", True),
        time_limit_minutes=float(tlm) if tlm is not None else None,
        locale=locale_val,
        interview_mode=mode_val,
        created_at=now,
    )
    db.add(position)

    prompt_text = (payload.get("prompt") or "").strip()
    if prompt_text:
        prompt = InterviewPrompt(
            id=str(uuid.uuid4()),
            position_id=position.id,
            interviewee_id=None,
            instructions=prompt_text,
            version=1,
            is_active=True,
            created_at=now,
        )
        db.add(prompt)

    await db.commit()
    await db.refresh(position)
    return await _position_to_api_dict(db, position)


@router.get("/{position_id}")
async def get_position(
    position_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    position = await db.scalar(select(Position).where(Position.id == position_id))
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    return await _position_to_api_dict(db, position)


@router.put("/{position_id}")
async def update_position(
    position_id: str,
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    position = await db.scalar(select(Position).where(Position.id == position_id))
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    if "title" in payload:
        position.title = payload["title"].strip()
    if "department" in payload:
        position.department = (payload["department"] or "").strip() or None
    if "description" in payload:
        position.description = (payload["description"] or "").strip() or None
    if "is_active" in payload:
        position.is_active = bool(payload["is_active"])
    if "time_limit_minutes" in payload:
        tlm = payload["time_limit_minutes"]
        position.time_limit_minutes = float(tlm) if tlm is not None else None
    if "locale" in payload:
        position.locale = (payload["locale"] or "").strip() or "ru"
    if "interview_mode" in payload:
        mode_val = (payload["interview_mode"] or "").strip() or "both"
        if mode_val in ("text", "voice", "both"):
            position.interview_mode = mode_val

    if "prompt" in payload:
        await _upsert_position_prompt(db, position_id, payload.get("prompt"))

    position.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(position)
    return await _position_to_api_dict(db, position)


@router.delete("/{position_id}")
async def delete_position(
    position_id: str,
    db: AsyncSession = Depends(get_db),
):
    from server.models.interviewee import Interviewee
    from server.models.interview_session import InterviewSession

    position = await db.scalar(select(Position).where(Position.id == position_id))
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    interviewee_count = await db.scalar(
        select(func.count()).select_from(Interviewee).where(
            Interviewee.position_id == position_id
        )
    ) or 0

    if interviewee_count > 0:
        in_progress = await db.scalar(
            select(func.count()).select_from(InterviewSession).where(
                InterviewSession.interviewee_id.in_(
                    select(Interviewee.id).where(Interviewee.position_id == position_id)
                ),
                InterviewSession.status == "in_progress",
            )
        ) or 0
        completed = await db.scalar(
            select(func.count()).select_from(InterviewSession).where(
                InterviewSession.interviewee_id.in_(
                    select(Interviewee.id).where(Interviewee.position_id == position_id)
                ),
                InterviewSession.status == "completed",
            )
        ) or 0
        return JSONResponse(
            status_code=409,
            content={
                "detail": {
                    "has_dependencies": True,
                    "candidate_count": interviewee_count,
                    "active_count": in_progress,
                    "completed_count": completed,
                }
            },
        )

    await db.delete(position)
    await db.commit()
    return JSONResponse(status_code=204, content=None)


@router.patch("/{position_id}/archive")
async def archive_position(
    position_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    from server.models.invite_link import InviteLink

    position = await db.scalar(select(Position).where(Position.id == position_id))
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    position.is_active = False
    position.updated_at = datetime.now(timezone.utc)

    active_links = list(
        await db.scalars(
            select(InviteLink).where(
                InviteLink.position_id == position_id,
                InviteLink.status == "active",
            )
        )
    )
    for link in active_links:
        link.status = "revoked"

    await db.commit()
    await db.refresh(position)
    return await _position_to_api_dict(db, position)


@router.patch("/{position_id}/restore")
async def restore_position(
    position_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    position = await db.scalar(select(Position).where(Position.id == position_id))
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    position.is_active = True
    position.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(position)
    return await _position_to_api_dict(db, position)


_LOCALE_NAMES = {"ru": "Russian", "en": "English"}


@router.post("/generate-prompt")
async def generate_interview_prompt(payload: Dict[str, Any]) -> Dict[str, str]:
    """Use OpenAI to generate a structured interview prompt from a job title."""
    from server.openai_client import chat_completion

    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")

    department = (payload.get("department") or "").strip()
    description = (payload.get("description") or "").strip()
    locale = (payload.get("locale") or "").strip() or "ru"
    lang_name = _LOCALE_NAMES.get(locale, locale)

    user_msg = f"Job title: {title}"
    if department:
        user_msg += f"\nDepartment: {department}"
    if description:
        user_msg += f"\nAdditional requirements and context:\n{description}"

    instructions = _META_PROMPT + f"\n\nGenerate the output entirely in {lang_name} language."

    try:
        prompt_text = await chat_completion(
            messages=[{"role": "user", "content": user_msg}],
            instructions=instructions,
        )
    except Exception as exc:
        logger.exception("Prompt generation failed for title=%s", title)
        raise HTTPException(status_code=502, detail=f"OpenAI error: {exc}") from exc

    return {"prompt": prompt_text.strip()}


# ─── Position criteria CRUD ────────────────────────────────────────

@router.get("/{position_id}/criteria")
async def list_position_criteria(
    position_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return criteria for a position. Falls back to global criteria if none set."""
    position = await db.scalar(select(Position).where(Position.id == position_id))
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    rows = list(
        await db.scalars(
            select(AssessmentCriterion)
            .where(
                AssessmentCriterion.position_id == position_id,
                AssessmentCriterion.is_active == True,
            )
            .order_by(AssessmentCriterion.display_order)
        )
    )

    if not rows:
        rows = list(
            await db.scalars(
                select(AssessmentCriterion)
                .where(
                    AssessmentCriterion.position_id.is_(None),
                    AssessmentCriterion.is_active == True,
                )
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
            "is_global": c.position_id is None,
        }
        for c in rows
    ]


@router.put("/{position_id}/criteria")
async def save_position_criteria(
    position_id: str,
    payload: List[Dict[str, Any]],
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Replace all position-specific criteria with the supplied list."""
    position = await db.scalar(select(Position).where(Position.id == position_id))
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")

    existing = list(
        await db.scalars(
            select(AssessmentCriterion).where(
                AssessmentCriterion.position_id == position_id
            )
        )
    )
    for old in existing:
        await db.delete(old)

    now = datetime.now(timezone.utc)
    result = []
    for i, c in enumerate(payload):
        name = (str(c.get("name", "")).strip()) or f"Criterion {i+1}"
        row = AssessmentCriterion(
            id=str(uuid.uuid4()),
            name=name,
            description=(str(c.get("description", "")).strip()) or None,
            max_score=float(c.get("max_score", 10.0)),
            weight=max(0.1, min(5.0, float(c.get("weight", 1.0)))),
            is_active=True,
            display_order=i,
            position_id=position_id,
            created_at=now,
        )
        db.add(row)
        result.append({
            "id": row.id,
            "name": row.name,
            "description": row.description,
            "max_score": row.max_score,
            "weight": row.weight,
            "display_order": row.display_order,
            "is_global": False,
        })

    await db.commit()
    return result


_CRITERIA_META_PROMPT = """\
You are an expert HR consultant.

Given a job title (and optionally a department, job description, or interview prompt), \
generate 4-7 assessment criteria that a recruiter should use to evaluate candidates \
for this specific role.

Each criterion must have:
- name: short label (2-4 words), e.g. "Sales Skills", "Technical Knowledge"
- description: one sentence explaining what to evaluate
- weight: a number from 0.5 to 2.0 indicating relative importance (1.0 = normal)

Adapt criteria to the role. For example:
- A developer role should have "Coding Skills", "System Design", "Problem Solving"
- A sales role should have "Negotiation", "Customer Empathy", "Objection Handling"
- A nurse role should have "Patient Care", "Clinical Knowledge", "Stress Management"

Respond ONLY with valid JSON array, no markdown, no commentary:
[
  {"name": "...", "description": "...", "weight": 1.0},
  ...
]\
"""


@router.post("/generate-criteria")
async def generate_criteria(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Use OpenAI to generate assessment criteria for a position."""
    from server.openai_client import chat_completion
    import json as _json

    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="title is required")

    department = (payload.get("department") or "").strip()
    description = (payload.get("description") or "").strip()
    locale = (payload.get("locale") or "").strip() or "ru"
    lang_name = _LOCALE_NAMES.get(locale, locale)

    user_msg = f"Job title: {title}"
    if department:
        user_msg += f"\nDepartment: {department}"
    if description:
        user_msg += f"\nAdditional context:\n{description}"

    instructions = _CRITERIA_META_PROMPT + f"\n\nGenerate the output entirely in {lang_name} language."

    try:
        raw = await chat_completion(
            messages=[{"role": "user", "content": user_msg}],
            instructions=instructions,
        )
    except Exception as exc:
        logger.exception("Criteria generation failed for title=%s", title)
        raise HTTPException(status_code=502, detail=f"OpenAI error: {exc}") from exc

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [ln for ln in lines if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        criteria = _json.loads(cleaned)
    except _json.JSONDecodeError as exc:
        logger.error("Failed to parse criteria JSON: %s", exc)
        raise HTTPException(status_code=502, detail="AI returned invalid JSON") from exc

    if not isinstance(criteria, list):
        raise HTTPException(status_code=502, detail="AI returned non-array JSON")

    result = []
    for i, c in enumerate(criteria):
        result.append({
            "name": str(c.get("name", f"Criterion {i+1}")).strip(),
            "description": str(c.get("description", "")).strip(),
            "weight": max(0.1, min(5.0, float(c.get("weight", 1.0)))),
        })
    return result


def _extract_text_from_docx(data: bytes) -> str:
    import docx
    doc = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_text_from_pdf(data: bytes) -> str:
    import pdfplumber
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


_ALLOWED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}
_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/upload-description")
async def upload_description(file: UploadFile = File(...)) -> Dict[str, str]:
    """Extract text from an uploaded .docx or .pdf file."""
    ct = (file.content_type or "").lower()
    fname = (file.filename or "").lower()

    is_pdf = ct == "application/pdf" or fname.endswith(".pdf")
    is_docx = (
        ct in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        )
        or fname.endswith(".docx")
        or fname.endswith(".doc")
    )

    if not is_pdf and not is_docx:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Please upload .pdf or .docx",
        )

    data = await file.read()
    if len(data) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 10 MB)")

    try:
        if is_pdf:
            text = _extract_text_from_pdf(data)
        else:
            text = _extract_text_from_docx(data)
    except Exception as exc:
        logger.exception("Failed to extract text from uploaded file")
        raise HTTPException(status_code=422, detail=f"Cannot read file: {exc}") from exc

    if not text.strip():
        raise HTTPException(status_code=422, detail="No text could be extracted from this file")

    return {"text": text.strip()}
