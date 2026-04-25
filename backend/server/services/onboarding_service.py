"""Onboarding domain service — DB operations for employee plans."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.models.onboarding import OnboardingPlan, OnboardingTask
from server.services.knowledge_service import ChatReply


@dataclass
class PlanSummary:
    plan_id: str
    title: str
    stage: str
    total: int
    done: int
    next_task: str | None
    tasks: list[dict[str, Any]] = field(default_factory=list)


class OnboardingService:
    async def get_employee_plan(
        self,
        db: AsyncSession,
        employee_id: str,
    ) -> PlanSummary | None:
        plan = await db.scalar(
            select(OnboardingPlan)
            .where(
                OnboardingPlan.employee_id == employee_id,
                OnboardingPlan.status == "active",
            )
            .order_by(OnboardingPlan.created_at.desc())
        )
        if not plan:
            return None

        tasks = list(
            await db.scalars(
                select(OnboardingTask).where(OnboardingTask.plan_id == plan.id)
            )
        )
        done_tasks = [t for t in tasks if t.status == "done"]
        pending = [t for t in tasks if t.status == "pending"]

        return PlanSummary(
            plan_id=plan.id,
            title=plan.title,
            stage=plan.stage,
            total=len(tasks),
            done=len(done_tasks),
            next_task=pending[0].title if pending else None,
            tasks=[
                {
                    "id": t.id,
                    "title": t.title,
                    "status": t.status,
                    "due_date": t.due_date.isoformat() if t.due_date else None,
                }
                for t in tasks
            ],
        )

    def format_reply(self, summary: PlanSummary | None, employee_id: str) -> ChatReply:
        if summary is None:
            return ChatReply(
                text="Для вас ещё не создан план адаптации. Обратитесь к HR-менеджеру.",
                card_type="text",
            )

        stage_names = {"day1": "1-й день", "week1": "1-я неделя", "month1": "1-й месяц"}
        stage_label = stage_names.get(summary.stage, summary.stage)

        progress_pct = int(summary.done / summary.total * 100) if summary.total else 0
        next_msg = f"\nСледующая задача: {summary.next_task}" if summary.next_task else "\nВсе задачи выполнены!"

        text = (
            f"Ваш план адаптации «{summary.title}» (этап: {stage_label}).\n"
            f"Выполнено: {summary.done} из {summary.total} задач ({progress_pct}%).{next_msg}"
        )

        return ChatReply(
            text=text,
            card_type="onboarding_plan",
            metadata={
                "plan_id": summary.plan_id,
                "stage": summary.stage,
                "progress": progress_pct,
                "done": summary.done,
                "total": summary.total,
                "tasks": summary.tasks,
                "quick_replies": ["Отметить выполненным", "Показать все задачи", "Задать вопрос"],
            },
        )
