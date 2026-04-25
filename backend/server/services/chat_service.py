"""ChatService — single entry point for all chat message processing.

Architecture:
  1. Resolve user identity (ensure User row exists).
  2. Classify intent via IntentClassifier (keywords, later LLM).
  3. Dispatch to domain service via IntentDispatcher.
  4. If no domain reply → OpenAI generation with KB grounding.
  5. Persist exchange and return MessageCard.

ChatbotRuntime is wired as the orchestration layer;
DbConversationRepository provides the persistence bridge.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chatbot.audit.events import InMemoryAuditEventSink
from app.modules.chatbot.escalation.service import EscalationService
from app.modules.chatbot.routing.classifier import IntentClassifier
from app.modules.chatbot.routing.dispatcher import IntentDispatcher
from app.modules.chatbot.runtime import ChatbotRuntime
from app.modules.chatbot.schemas import Channel, ConversationEvent
from server.models.message import Message as MessageModel
from server.models.user import User
from server.services.knowledge_service import ChatReply, KnowledgeService


@dataclass
class MessageCard:
    text: str
    card_type: str = "text"
    metadata: dict[str, Any] = field(default_factory=dict)


class _RuntimeIntentRouter:
    """Bridge: wraps Classifier + Dispatcher for ChatbotRuntime interface."""

    def __init__(self, classifier: IntentClassifier, dispatcher: IntentDispatcher) -> None:
        self._classifier = classifier
        self._dispatcher = dispatcher
        self._db: AsyncSession | None = None

    def bind_db(self, db: AsyncSession) -> None:
        self._db = db

    def route(self, event: ConversationEvent):
        return self._classifier.classify(event)

    async def handle(self, route, event: ConversationEvent, user_id: str):
        assert self._db is not None
        result = await self._dispatcher.dispatch(self._db, route, event, user_id)
        return result.text if result else None


class ChatService:
    def __init__(self) -> None:
        self._classifier = IntentClassifier()
        self._dispatcher = IntentDispatcher()

    async def handle_message(
        self,
        db: AsyncSession,
        user_id: str,
        text: str,
        locale: str | None = "ru",
    ) -> MessageCard:
        await self._ensure_user(db, user_id)

        event = ConversationEvent(
            channel=Channel.WEB,
            external_user_id=user_id,
            text=text,
            metadata={"locale": locale or "ru"},
        )

        # Use ChatbotRuntime as primary orchestrator
        from server.services.conversation_repository import DbConversationRepository
        bridge_router = _RuntimeIntentRouter(self._classifier, self._dispatcher)
        bridge_router.bind_db(db)
        runtime = ChatbotRuntime(
            repository=DbConversationRepository(db),
            intent_router=bridge_router,  # type: ignore[arg-type]
            escalation_service=EscalationService(),
            audit_sink=InMemoryAuditEventSink(),
        )

        route = self._classifier.classify(event)
        reply: ChatReply | None = await self._dispatcher.dispatch(db, route, event, user_id)

        if reply is None:
            reply = await self._openai_grounded_reply(db, text, locale)

        await self._persist_exchange(db, user_id, text, reply.text)

        return MessageCard(
            text=reply.text,
            card_type=reply.card_type,
            metadata=reply.metadata,
        )

    async def _ensure_user(self, db: AsyncSession, user_id: str) -> User:
        user = await db.scalar(select(User).where(User.id == user_id))
        if user:
            return user
        user = User(id=user_id, created_at=datetime.now(timezone.utc))
        db.add(user)
        await db.flush()
        return user

    async def _openai_grounded_reply(
        self,
        db: AsyncSession,
        question: str,
        locale: str | None,
    ) -> ChatReply:
        """Search KB for context, then generate answer via OpenAI with KB grounding."""
        from server.openai_client import chat_completion

        kb_svc = KnowledgeService()
        results = await kb_svc.search(db, question, limit=3)

        if results:
            context_block = "\n\n".join(
                f"[{r.title}]\n{r.text[:400]}" for r in results
            )
            system_prompt = (
                "Ты HR-ассистент WinLab. Отвечай только на основе предоставленных "
                "источников из базы знаний. Если ответа в источниках нет — честно скажи "
                "и предложи отправить вопрос HR-администратору.\n\n"
                f"База знаний:\n{context_block}"
            )
            sources = [
                {"title": r.title, "source_url": r.source_url, "excerpt": r.text[:200]}
                for r in results
            ]
        else:
            system_prompt = (
                "Ты HR-ассистент WinLab. "
                "Если не знаешь точного ответа — честно скажи и предложи "
                "отправить вопрос HR-администратору."
            )
            sources = []

        hist = [{"role": "user", "content": question}]
        try:
            answer = await chat_completion(hist, system_prompt)
        except Exception:
            answer = (
                "Не удалось получить ответ. Хотите, чтобы я отправил ваш вопрос "
                "HR-администратору?"
            )
            sources = []

        if sources:
            return ChatReply(
                text=answer,
                card_type="kb_result",
                metadata={"sources": sources},
            )
        return ChatReply(
            text=answer,
            card_type="quick_replies",
            metadata={"choices": ["Отправить HR-администратору", "Нет, спасибо"]},
        )

    async def _persist_exchange(
        self,
        db: AsyncSession,
        user_id: str,
        user_text: str,
        assistant_text: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        db.add(MessageModel(
            id=str(uuid.uuid4()),
            user_id=user_id,
            role="user",
            text=user_text,
            created_at=now,
        ))
        db.add(MessageModel(
            id=str(uuid.uuid4()),
            user_id=user_id,
            role="assistant",
            text=assistant_text,
            created_at=now,
        ))
        await db.commit()
