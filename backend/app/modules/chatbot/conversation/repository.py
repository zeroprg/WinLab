"""Conversation persistence repository contracts and in-memory implementation."""

from __future__ import annotations

from typing import Protocol

from app.modules.chatbot.schemas import (
    ConversationMessage,
    ConversationSession,
)


class ConversationRepository(Protocol):
    def get_session(self, session_id: str) -> ConversationSession | None:
        """Return a session by internal id."""

    def save_session(self, session: ConversationSession) -> None:
        """Persist a session."""

    def add_message(self, message: ConversationMessage) -> None:
        """Append a message to a session transcript."""

    def list_messages(self, session_id: str) -> list[ConversationMessage]:
        """Return transcript messages for the session."""


class InMemoryConversationRepository:
    def __init__(self) -> None:
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

