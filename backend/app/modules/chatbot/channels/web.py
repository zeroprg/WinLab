"""Web chat channel adapter."""

from __future__ import annotations

from typing import Any, Mapping

from app.modules.chatbot.schemas import Channel, ConversationEvent


class WebChannel:
    name = Channel.WEB.value

    def normalize_event(self, payload: Mapping[str, Any]) -> ConversationEvent:
        return ConversationEvent(
            channel=Channel.WEB,
            external_user_id=str(payload["external_user_id"]),
            text=str(payload.get("text", "")),
            external_message_id=(
                str(payload["message_id"]) if payload.get("message_id") else None
            ),
            session_external_id=(
                str(payload["session_id"]) if payload.get("session_id") else None
            ),
            metadata=dict(payload.get("metadata") or {}),
        )

    async def send_text(
        self,
        *,
        external_user_id: str,
        text: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        _ = (external_user_id, text, metadata)

