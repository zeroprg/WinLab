"""Chatbot API route wiring placeholder.

This module intentionally avoids binding to FastAPI until the application shell
is introduced. The pure function below is the first vertical slice:
payload -> channel adapter -> chatbot runtime -> response text.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.modules.chatbot.audit.events import InMemoryAuditEventSink
from app.modules.chatbot.channels.web import WebChannel
from app.modules.chatbot.conversation.repository import InMemoryConversationRepository
from app.modules.chatbot.escalation.service import EscalationService
from app.modules.chatbot.routing.intent_router import IntentRouter
from app.modules.chatbot.runtime import ChatbotRuntime


def handle_web_chat_message(payload: Mapping[str, Any]) -> str:
    channel = WebChannel()
    runtime = ChatbotRuntime(
        repository=InMemoryConversationRepository(),
        intent_router=IntentRouter(),
        escalation_service=EscalationService(),
        audit_sink=InMemoryAuditEventSink(),
    )
    event = channel.normalize_event(payload)
    response = runtime.handle_event(event)
    return response.message.text

