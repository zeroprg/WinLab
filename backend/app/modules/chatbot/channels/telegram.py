"""Future Telegram channel adapter."""

from __future__ import annotations

from typing import Any, Mapping

from app.modules.chatbot.schemas import Channel, ConversationEvent


class TelegramChannel:
    name = Channel.TELEGRAM.value

    def normalize_event(self, payload: Mapping[str, Any]) -> ConversationEvent:
        message = payload.get("message") or {}
        sender = message.get("from") or {}
        chat = message.get("chat") or {}
        return ConversationEvent(
            channel=Channel.TELEGRAM,
            external_user_id=str(sender.get("id") or payload["external_user_id"]),
            text=str(message.get("text") or payload.get("text") or ""),
            external_message_id=(
                str(message["message_id"]) if message.get("message_id") else None
            ),
            session_external_id=(str(chat["id"]) if chat.get("id") else None),
            metadata=dict(payload),
        )

    async def send_text(
        self,
        *,
        external_user_id: str,
        text: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        _ = (external_user_id, text, metadata)

