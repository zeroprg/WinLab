"""Conversation state helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.modules.chatbot.schemas import ConversationStatus, IntentType


@dataclass(slots=True)
class ConversationRuntimeState:
    status: ConversationStatus = ConversationStatus.ACTIVE
    current_intent: IntentType = IntentType.UNKNOWN
    pending_confirmation: str | None = None
    context: dict[str, Any] = field(default_factory=dict)

    def require_consent(self, reason: str) -> None:
        self.status = ConversationStatus.WAITING_FOR_CONSENT
        self.pending_confirmation = reason

    def mark_escalated(self) -> None:
        self.status = ConversationStatus.ESCALATED
        self.pending_confirmation = None

