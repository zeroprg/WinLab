"""Minimal chatbot runtime for the first vertical slice.

The runtime owns orchestration only. Domain behavior remains behind RAG,
HR tools, onboarding, surveys, and escalation boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.chatbot.audit.events import AuditEvent, AuditEventSink
from app.modules.chatbot.conversation.repository import ConversationRepository
from app.modules.chatbot.escalation.service import EscalationService
from app.modules.chatbot.routing.intent_router import IntentRouter
from app.modules.chatbot.routing.policies import HrAssistantBotPolicy
from app.modules.chatbot.schemas import (
    ConversationEvent,
    ConversationMessage,
    ConversationSession,
    IntentType,
    ParticipantRole,
)


@dataclass(slots=True)
class ChatbotResponse:
    session: ConversationSession
    message: ConversationMessage


class ChatbotRuntime:
    def __init__(
        self,
        *,
        repository: ConversationRepository,
        intent_router: IntentRouter,
        escalation_service: EscalationService,
        audit_sink: AuditEventSink,
        policy: HrAssistantBotPolicy | None = None,
    ) -> None:
        self.repository = repository
        self.intent_router = intent_router
        self.escalation_service = escalation_service
        self.audit_sink = audit_sink
        self.policy = policy or HrAssistantBotPolicy()

    def handle_event(self, event: ConversationEvent) -> ChatbotResponse:
        session = ConversationSession(
            channel=event.channel,
            external_user_id=event.external_user_id,
            metadata={
                "external_message_id": event.external_message_id,
                "session_external_id": event.session_external_id,
            },
        )
        self.repository.save_session(session)

        user_message = ConversationMessage(
            session_id=session.id,
            role=ParticipantRole.USER,
            text=event.text,
            metadata=dict(event.metadata),
        )
        self.repository.add_message(user_message)

        route = self.intent_router.route(event)
        decision = self.policy.check(route)
        self.audit_sink.record(
            AuditEvent(
                event_type="chatbot.intent_routed",
                actor_id=event.external_user_id,
                session_id=session.id,
                metadata={
                    "intent": route.intent.value,
                    "confidence": route.confidence,
                    "allowed": decision.allowed,
                    "reason": route.reason,
                },
            )
        )

        if not decision.allowed:
            response_text = "Этот запрос нельзя обработать в текущем контексте."
        elif route.intent == IntentType.KNOWLEDGE:
            response_text = (
                "Я проверю утвержденную базу знаний WinLab и отвечу "
                "со ссылками на источники."
            )
        elif route.intent == IntentType.HR_SELF_SERVICE:
            response_text = (
                "Это кадровый запрос. Я выполню его через защищенный HR tool "
                "с проверкой прав доступа и аудитом."
            )
        elif route.intent == IntentType.ONBOARDING:
            response_text = (
                "Это вопрос по адаптации. Я открою соответствующий onboarding "
                "сценарий и покажу следующий шаг."
            )
        elif route.intent == IntentType.SURVEY:
            response_text = "Это ответ/запрос по опросу. Я передам его в Surveys module."
        else:
            ticket = self.escalation_service.create_ticket(
                session_id=session.id,
                question=event.text,
                consent_given=False,
            )
            response_text = (
                "Я не уверен в ответе. Могу отправить вопрос HR-администратору "
                f"после вашего подтверждения. Черновик обращения: {ticket.id}."
            )

        assistant_message = ConversationMessage(
            session_id=session.id,
            role=ParticipantRole.ASSISTANT,
            text=response_text,
            metadata={"intent": route.intent.value},
        )
        self.repository.add_message(assistant_message)

        return ChatbotResponse(session=session, message=assistant_message)

