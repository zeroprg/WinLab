"""Chatbot audit event contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

from app.modules.chatbot.schemas import new_id


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_type: str
    actor_id: str | None
    session_id: str | None
    id: str = field(default_factory=lambda: new_id("audit"))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    pii_scope: str = "none"
    metadata: Mapping[str, Any] = field(default_factory=dict)


class AuditEventSink(Protocol):
    def record(self, event: AuditEvent) -> None:
        """Persist or dispatch an audit event."""


class InMemoryAuditEventSink:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def record(self, event: AuditEvent) -> None:
        self.events.append(event)

