"""Intent router foundation."""

from __future__ import annotations

from app.modules.chatbot.schemas import ConversationEvent, IntentRoute, IntentType


class IntentRouter:
    """Deterministic baseline router before ML/LLM classification is added."""

    def route(self, event: ConversationEvent) -> IntentRoute:
        text = event.text.lower()

        if any(word in text for word in ("отпуск", "зарплат", "час", "справк")):
            return IntentRoute(
                intent=IntentType.HR_SELF_SERVICE,
                confidence=0.75,
                reason="Matched HR self-service keywords.",
            )

        if any(word in text for word in ("адаптац", "первый день", "обучен")):
            return IntentRoute(
                intent=IntentType.ONBOARDING,
                confidence=0.7,
                reason="Matched onboarding keywords.",
            )

        if any(word in text for word in ("опрос", "feedback", "exit")):
            return IntentRoute(
                intent=IntentType.SURVEY,
                confidence=0.7,
                reason="Matched survey keywords.",
            )

        if event.text.strip():
            return IntentRoute(
                intent=IntentType.KNOWLEDGE,
                confidence=0.55,
                reason="Default to knowledge/RAG for non-empty message.",
            )

        return IntentRoute(
            intent=IntentType.UNKNOWN,
            confidence=0.0,
            reason="Empty message.",
        )

