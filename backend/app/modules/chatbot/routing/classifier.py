"""Intent classifier — single responsibility: classify text into an IntentRoute.

Keyword classification is the baseline. LLM-based classification
(OpenAI function calling) is added in Phase 3 as an optional fallback
for low-confidence keyword matches.
"""
from __future__ import annotations

from app.modules.chatbot.schemas import ConversationEvent, IntentRoute, IntentType

_HR_KEYWORDS = (
    "отпуск", "зарплат", "час", "справк", "оклад",
    "начислен", "отработан", "выплат", "больничн",
)
_ONBOARDING_KEYWORDS = (
    "адаптац", "первый день", "план", "задач",
    "обучен", "онбординг", "испытательн", "новичок",
)
_SURVEY_KEYWORDS = (
    "опрос", "feedback", "exit", "анкет",
    "обратная связь", "satisfaction",
)


class IntentClassifier:
    """Classify a ConversationEvent into an IntentRoute."""

    def classify(self, event: ConversationEvent) -> IntentRoute:
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
