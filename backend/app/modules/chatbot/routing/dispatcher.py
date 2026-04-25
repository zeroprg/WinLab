"""Intent dispatcher — routes classified intents to domain handlers.

The dispatcher owns no business logic and no DB access directly.
It delegates to domain services via dependency injection,
receiving an AsyncSession as a parameter.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chatbot.schemas import IntentRoute, IntentType, ConversationEvent


class IntentDispatcher:
    """Route an IntentRoute to the correct domain service handler."""

    async def dispatch(
        self,
        db: AsyncSession,
        route: IntentRoute,
        event: ConversationEvent,
        user_id: str,
    ):
        """Return a ChatReply or None (caller handles escalation)."""
        from server.services.knowledge_service import KnowledgeService, ChatReply
        from server.services.onboarding_service import OnboardingService

        if route.intent == IntentType.KNOWLEDGE:
            svc = KnowledgeService()
            results = await svc.search(db, event.text)
            return svc.format_reply(results)

        if route.intent == IntentType.ONBOARDING:
            svc = OnboardingService()
            summary = await svc.get_employee_plan(db, user_id)
            return svc.format_reply(summary, user_id)

        if route.intent == IntentType.HR_SELF_SERVICE:
            return ChatReply(
                text=(
                    "Это кадровый запрос. Интеграция с 1C будет в Phase 4. "
                    "Хотите отправить запрос HR-администратору?"
                ),
                card_type="quick_replies",
                metadata={"choices": ["Да, отправить HR", "Нет, спасибо"]},
            )

        if route.intent == IntentType.SURVEY:
            return ChatReply(
                text="Модуль опросов будет доступен в Phase 5.",
                card_type="text",
            )

        return None  # unknown — caller handles escalation + consent
