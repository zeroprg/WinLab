"""Intent router with keyword classification and domain dispatch."""

from __future__ import annotations

from app.modules.chatbot.schemas import ConversationEvent, IntentRoute, IntentType

_HR_KEYWORDS = ("отпуск", "зарплат", "час", "справк", "оклад", "начислен", "отработан")
_ONBOARDING_KEYWORDS = ("адаптац", "первый день", "план", "задач", "обучен", "онбординг")
_SURVEY_KEYWORDS = ("опрос", "feedback", "exit", "анкет", "обратная связь")


class IntentRouter:
    """Keyword-based router. Extended by domain handlers via `handle()`."""

    def route(self, event: ConversationEvent) -> IntentRoute:
        text = event.text.lower()

        if any(w in text for w in _HR_KEYWORDS):
            return IntentRoute(
                intent=IntentType.HR_SELF_SERVICE,
                confidence=0.80,
                reason="Matched HR self-service keywords.",
            )

        if any(w in text for w in _ONBOARDING_KEYWORDS):
            return IntentRoute(
                intent=IntentType.ONBOARDING,
                confidence=0.75,
                reason="Matched onboarding keywords.",
            )

        if any(w in text for w in _SURVEY_KEYWORDS):
            return IntentRoute(
                intent=IntentType.SURVEY,
                confidence=0.70,
                reason="Matched survey keywords.",
            )

        if event.text.strip():
            return IntentRoute(
                intent=IntentType.KNOWLEDGE,
                confidence=0.60,
                reason="Default to knowledge/RAG for non-empty message.",
            )

        return IntentRoute(
            intent=IntentType.UNKNOWN,
            confidence=0.0,
            reason="Empty message.",
        )

    async def handle(self, route: IntentRoute, event: ConversationEvent, user_id: str) -> str:
        """Dispatch to domain handlers and return a response string."""
        if route.intent == IntentType.KNOWLEDGE:
            return await self._handle_knowledge(event.text)
        if route.intent == IntentType.ONBOARDING:
            return await self._handle_onboarding(user_id)
        if route.intent == IntentType.HR_SELF_SERVICE:
            return (
                "Это кадровый запрос. Я выполню его через защищённый HR-tool "
                "с проверкой прав доступа. Интеграция с 1C будет доступна в Phase 4."
            )
        if route.intent == IntentType.SURVEY:
            return "Это запрос по опросу. Модуль опросов будет доступен в Phase 5."
        return None  # escalate

    async def _handle_knowledge(self, question: str) -> str:
        """Search knowledge base directly via DB."""
        try:
            from server.db import get_session_factory
            from server.models.knowledge import KnowledgeChunk, KnowledgeDocument
            from sqlalchemy import select
            pattern = f"%{question[:100]}%"
            factory = get_session_factory()
            async with factory() as db:
                stmt = (
                    select(KnowledgeChunk)
                    .join(KnowledgeDocument)
                    .where(
                        KnowledgeDocument.status == "published",
                        KnowledgeChunk.text.like(pattern),
                    )
                    .limit(3)
                )
                chunks = list(await db.scalars(stmt))
                if not chunks:
                    doc_stmt = (
                        select(KnowledgeDocument)
                        .where(
                            KnowledgeDocument.status == "published",
                            KnowledgeDocument.content.like(pattern),
                        )
                        .limit(2)
                    )
                    docs = list(await db.scalars(doc_stmt))
                    if docs:
                        excerpts = "\n".join(f"• [{d.title}] {d.content[:200]}" for d in docs)
                        return f"Нашёл в базе знаний:\n{excerpts}"
                else:
                    excerpts = "\n".join(f"• {c.text[:200]}" for c in chunks[:2])
                    return f"Нашёл в базе знаний:\n{excerpts}"
        except Exception:
            pass
        return "По вашему вопросу информация пока не найдена в базе знаний. Хотите отправить вопрос HR-администратору?"

    async def _handle_onboarding(self, user_id: str) -> str:
        """Fetch employee's onboarding plan summary directly via DB."""
        try:
            from server.db import get_session_factory
            from server.models.onboarding import OnboardingPlan, OnboardingTask
            from sqlalchemy import select
            factory = get_session_factory()
            async with factory() as db:
                plan = await db.scalar(
                    select(OnboardingPlan)
                    .where(OnboardingPlan.employee_id == user_id, OnboardingPlan.status == "active")
                    .order_by(OnboardingPlan.created_at.desc())
                )
                if plan:
                    tasks = list(await db.scalars(
                        select(OnboardingTask).where(OnboardingTask.plan_id == plan.id)
                    ))
                    pending = [t for t in tasks if t.status == "pending"]
                    done_tasks = [t for t in tasks if t.status == "done"]
                    return (
                        f"Ваш план адаптации «{plan.title}» (этап: {plan.stage}).\n"
                        f"Выполнено задач: {len(done_tasks)} из {len(tasks)}.\n"
                        + (f"Следующая задача: {pending[0].title}" if pending else "Все задачи выполнены!")
                    )
        except Exception:
            pass
        return "Для вас ещё не создан план адаптации. Обратитесь к HR-менеджеру."

