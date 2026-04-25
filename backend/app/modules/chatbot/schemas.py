"""Chatbot public contracts.

These standard-library dataclasses keep the first implementation phase light:
the runtime can be wired and tested before a concrete API/ORM framework is
introduced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping
from uuid import uuid4


def new_id(prefix: str) -> str:
    """Create stable, readable IDs for early runtime contracts."""

    return f"{prefix}_{uuid4().hex}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Channel(str, Enum):
    WEB = "web"
    YANDEX = "yandex_messenger"
    TELEGRAM = "telegram"


class ParticipantRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    ADMIN = "admin"


class IntentType(str, Enum):
    KNOWLEDGE = "knowledge"
    HR_SELF_SERVICE = "hr_self_service"
    ONBOARDING = "onboarding"
    SURVEY = "survey"
    ESCALATION = "escalation"
    UNKNOWN = "unknown"


class ConversationStatus(str, Enum):
    ACTIVE = "active"
    WAITING_FOR_CONSENT = "waiting_for_consent"
    ESCALATED = "escalated"
    CLOSED = "closed"


@dataclass(slots=True)
class ConversationEvent:
    channel: Channel
    external_user_id: str
    text: str
    external_message_id: str | None = None
    session_external_id: str | None = None
    occurred_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ConversationMessage:
    session_id: str
    role: ParticipantRole
    text: str
    id: str = field(default_factory=lambda: new_id("msg"))
    created_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ConversationSession:
    channel: Channel
    external_user_id: str
    id: str = field(default_factory=lambda: new_id("conv"))
    employee_id: str | None = None
    candidate_id: str | None = None
    status: ConversationStatus = ConversationStatus.ACTIVE
    locale: str = "ru"
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class IntentRoute:
    intent: IntentType
    confidence: float
    reason: str
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolCall:
    name: str
    arguments: Mapping[str, Any]
    idempotency_key: str | None = None
    pii_scope: str = "none"


@dataclass(slots=True)
class ToolResult:
    success: bool
    data: Mapping[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    message: str | None = None
    retryable: bool = False


@dataclass(slots=True)
class EscalationTicket:
    session_id: str
    question: str
    consent_given: bool
    id: str = field(default_factory=lambda: new_id("esc"))
    status: str = "open"
    assignee_id: str | None = None
    created_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, Any] = field(default_factory=dict)

