"""Bot policy separation contracts."""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.chatbot.schemas import IntentRoute, IntentType


@dataclass(frozen=True, slots=True)
class BotPolicyDecision:
    allowed: bool
    reason: str


class RecruitingBotPolicy:
    """Policy boundary for interview-specific chatbot behavior."""

    allowed_intents = {IntentType.KNOWLEDGE}

    def check(self, route: IntentRoute) -> BotPolicyDecision:
        return BotPolicyDecision(
            allowed=route.intent in self.allowed_intents,
            reason="Recruiting policy allows only interview-safe intents.",
        )


class HrAssistantBotPolicy:
    """Policy boundary for employee HR assistant behavior."""

    allowed_intents = {
        IntentType.KNOWLEDGE,
        IntentType.HR_SELF_SERVICE,
        IntentType.ONBOARDING,
        IntentType.SURVEY,
        IntentType.ESCALATION,
        IntentType.UNKNOWN,
    }

    def check(self, route: IntentRoute) -> BotPolicyDecision:
        return BotPolicyDecision(
            allowed=route.intent in self.allowed_intents,
            reason="HR assistant policy allows HR chatbot intents.",
        )

