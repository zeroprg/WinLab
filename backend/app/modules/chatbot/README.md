# Chatbot Module

Owns conversation orchestration: channels, conversation state, intent routing, tool execution, escalation, and audit events.

The chatbot module must not own 1C, onboarding, surveys, recruiting, or knowledge business logic directly. It orchestrates those modules through explicit interfaces.

