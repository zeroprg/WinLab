"""Yandex Messenger channel adapter."""

from __future__ import annotations

from typing import Any, Mapping

from app.modules.chatbot.schemas import Channel, ConversationEvent


class YandexMessengerChannel:
    name = Channel.YANDEX.value

    def normalize_event(self, payload: Mapping[str, Any]) -> ConversationEvent:
        sender = payload.get("sender") or {}
        message = payload.get("message") or {}
        chat = payload.get("chat") or {}
        return ConversationEvent(
            channel=Channel.YANDEX,
            external_user_id=str(sender.get("id") or payload["external_user_id"]),
            text=str(message.get("text") or payload.get("text") or ""),
            external_message_id=(
                str(message["id"]) if message.get("id") else None
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

