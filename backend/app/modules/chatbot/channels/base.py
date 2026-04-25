"""Channel adapter contracts."""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from app.modules.chatbot.schemas import ConversationEvent


class BotChannel(Protocol):
    """Adapter interface for all chatbot channels."""

    name: str

    def normalize_event(self, payload: Mapping[str, Any]) -> ConversationEvent:
        """Convert external webhook/request payload into a canonical event."""

    async def send_text(
        self,
        *,
        external_user_id: str,
        text: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        """Send a plain text response through the channel."""

