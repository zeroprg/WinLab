"""Onboarding API routes."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.db import get_db
from server.middleware.auth import get_current_user, require_admin
from server.models.onboarding import OnboardingPlan, OnboardingTask
from server.models.user import User

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])
employee_router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


def _plan_to_dict(plan: OnboardingPlan, tasks: List[OnboardingTask] | None = None) -> Dict[str, Any]:
    d: Dict[str, Any] = {
        "id": plan.id,
        "employee_id": plan.employee_id,
        "title": plan.title,
        "stage": plan.stage,
        "status": plan.status,
        "created_at": plan.created_at.isoformat() if plan.created_at else None,
        "updated_at": plan.updated_at.isoformat() if plan.updated_at else None,
    }
    if tasks is not None:
        d["tasks"] = [_task_to_dict(t) for t in tasks]
    return d


def _task_to_dict(t: OnboardingTask) -> Dict[str, Any]:
    return {
        "id": t.id,
        "plan_id": t.plan_id,
        "title": t.title,
        "description": t.description,
        "owner_id": t.owner_id,
        "due_date": t.due_date.isoformat() if t.due_date else None,
        "status": t.status,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
    }


@router.get("", dependencies=[Depends(require_admin)])
async def list_plans(
    employee_id: Optional[str] = None,
    stage: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    stmt = select(OnboardingPlan).order_by(OnboardingPlan.created_at.desc())
    if employee_id:
        stmt = stmt.where(OnboardingPlan.employee_id == employee_id)
    if stage:
        stmt = stmt.where(OnboardingPlan.stage == stage)
    plans = list(await db.scalars(stmt))
    result = []
    for plan in plans:
        tasks = list(await db.scalars(
            select(OnboardingTask).where(OnboardingTask.plan_id == plan.id)
        ))
        result.append(_plan_to_dict(plan, tasks))
    return result


@router.post("", status_code=201, dependencies=[Depends(require_admin)])
async def create_plan(
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    employee_id = str(payload.get("employee_id", "")).strip()
    if not employee_id:
        raise HTTPException(status_code=400, detail="employee_id is required")
    now = datetime.now(timezone.utc)
    plan = OnboardingPlan(
        id=str(uuid.uuid4()),
        employee_id=employee_id,
        title=payload.get("title", "Адаптация"),
        stage=payload.get("stage", "day1"),
        status="active",
        created_at=now,
    )
    db.add(plan)
    tasks_data = payload.get("tasks", [])
    tasks = []
    for td in tasks_data:
        due = None
        if td.get("due_date"):
            try:
                due = datetime.fromisoformat(td["due_date"])
            except ValueError:
                pass
        task = OnboardingTask(
            id=str(uuid.uuid4()),
            plan_id=plan.id,
            title=str(td.get("title", "")),
            description=td.get("description"),
            owner_id=td.get("owner_id"),
            due_date=due,
            status="pending",
            created_at=now,
        )
        db.add(task)
        tasks.append(task)
    await db.commit()
    await db.refresh(plan)
    return _plan_to_dict(plan, tasks)


@router.patch("/{plan_id}", dependencies=[Depends(require_admin)])
async def update_plan(
    plan_id: str,
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    plan = await db.scalar(select(OnboardingPlan).where(OnboardingPlan.id == plan_id))
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    for field in ("title", "stage", "status"):
        if field in payload:
            setattr(plan, field, payload[field])
    plan.updated_at = datetime.now(timezone.utc)
    await db.commit()
    tasks = list(await db.scalars(select(OnboardingTask).where(OnboardingTask.plan_id == plan_id)))
    return _plan_to_dict(plan, tasks)


@router.post("/{plan_id}/tasks", status_code=201, dependencies=[Depends(require_admin)])
async def add_task(
    plan_id: str,
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    plan = await db.scalar(select(OnboardingPlan).where(OnboardingPlan.id == plan_id))
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    due = None
    if payload.get("due_date"):
        try:
            due = datetime.fromisoformat(payload["due_date"])
        except ValueError:
            pass
    task = OnboardingTask(
        id=str(uuid.uuid4()),
        plan_id=plan_id,
        title=str(payload.get("title", "")),
        description=payload.get("description"),
        owner_id=payload.get("owner_id"),
        due_date=due,
        status="pending",
        created_at=datetime.now(timezone.utc),
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return _task_to_dict(task)


@employee_router.patch("/tasks/{task_id}")
async def update_task_status(
    task_id: str,
    payload: Dict[str, Any],
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Employee marks a task as in_progress or done."""
    task = await db.scalar(select(OnboardingTask).where(OnboardingTask.id == task_id))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    new_status = str(payload.get("status", "")).strip()
    if new_status not in ("pending", "in_progress", "done"):
        raise HTTPException(status_code=400, detail="Invalid status")
    task.status = new_status
    if new_status == "done":
        task.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return _task_to_dict(task)


@employee_router.get("/my/{employee_id}")
async def get_my_plan(
    employee_id: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Return employee's active onboarding plan with tasks."""
    plan = await db.scalar(
        select(OnboardingPlan)
        .where(OnboardingPlan.employee_id == employee_id, OnboardingPlan.status == "active")
        .order_by(OnboardingPlan.created_at.desc())
    )
    if not plan:
        raise HTTPException(status_code=404, detail="No active onboarding plan found")
    tasks = list(await db.scalars(select(OnboardingTask).where(OnboardingTask.plan_id == plan.id)))
    return _plan_to_dict(plan, tasks)
