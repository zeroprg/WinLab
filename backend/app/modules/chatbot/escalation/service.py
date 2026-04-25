"""Escalation service foundation."""

from __future__ import annotations

from app.modules.chatbot.schemas import EscalationTicket


class EscalationService:
    def __init__(self) -> None:
        self._tickets: dict[str, EscalationTicket] = {}

    def create_ticket(
        self,
        *,
        session_id: str,
        question: str,
        consent_given: bool,
    ) -> EscalationTicket:
        ticket = EscalationTicket(
            session_id=session_id,
            question=question,
            consent_given=consent_given,
        )
        self._tickets[ticket.id] = ticket
        return ticket

    def list_open(self) -> list[EscalationTicket]:
        return [ticket for ticket in self._tickets.values() if ticket.status == "open"]

