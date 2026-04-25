"""SQLAlchemy-backed ConversationRepository for ChatbotRuntime."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.chatbot.conversation.repository import ConversationRepository
from app.modules.chatbot.schemas import (
    ConversationMessage,
    ConversationSession,
    ParticipantRole,
)
from server.models.message import Message as MessageModel
from server.models.user import User


class DbConversationRepository:
    """Implements ConversationRepository protocol backed by SQLAlchemy.

    In-memory fallback is used for the ConversationSession itself
    (transient per-request), while ConversationMessage is persisted.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._sessions: dict[str, ConversationSession] = {}
        self._messages: dict[str, list[ConversationMessage]] = {}

    def get_session(self, session_id: str) -> ConversationSession | None:
        return self._sessions.get(session_id)

    def save_session(self, session: ConversationSession) -> None:
        self._sessions[session.id] = session

    def add_message(self, message: ConversationMessage) -> None:
        self._messages.setdefault(message.session_id, []).append(message)

    def list_messages(self, session_id: str) -> list[ConversationMessage]:
        return list(self._messages.get(session_id, []))
