# Chatbot Implementation Plan

## Goal

Create an executable project skeleton for the WinLab HR Super-App chatbot while keeping architecture boundaries explicit:

- `chatbot` orchestrates conversations;
- domain modules own business logic;
- `integrations` owns external systems;
- `shared` owns cross-cutting primitives;
- the current `ai-recruiter` bot/runtime is reused as a reference foundation, not copied blindly.

## Implementation Sequence

### Step 1: Project Skeleton

Create backend and frontend module folders with placeholder files and module READMEs.

Backend target:

```text
backend/app/
  main.py
  modules/
    chatbot/
    identity/
    recruiting/
    onboarding/
    preboarding/
    knowledge/
    surveys/
    integrations/
    analytics/
  shared/
    auth/
    db/
    events/
    schemas/
```

Frontend target:

```text
frontend/src/
  admin/
    chatbot/
    recruiting/
    onboarding/
    preboarding/
    knowledge/
    surveys/
  shared/
    api/
    components/
    layout/
```

### Step 2: Chatbot Runtime Foundation

Define the first contracts:

- `ConversationEvent`;
- `ConversationSession`;
- `ConversationMessage`;
- `BotChannel`;
- `IntentRouter`;
- `ToolRegistry`;
- `EscalationTicket`.

### Step 3: ai-recruiter Reuse Adapter

Add an adapter layer for concepts reused from `ai-recruiter`:

- existing chat session lifecycle pattern;
- message/transcript persistence pattern;
- OpenAI client wrapper pattern;
- web chat UX pattern.

Do not reuse interview-specific prompt flow as HR chatbot policy.

### Step 4: First Vertical Slice

Implement the minimum flow:

```text
Web/Yandex event -> Channel Gateway -> Chatbot Runtime -> Intent Router -> RAG stub -> response
```

### Step 5: Enterprise Flow

Extend with:

- HR tools via integrations;
- onboarding flows;
- survey flows;
- unresolved query + consent + escalation;
- audit and admin operations.

## Definition of Done

- Project skeleton exists under `WinLab/backend` and `WinLab/frontend`.
- Each backend domain module has clear ownership documented.
- Chatbot module has submodules for `channels`, `conversation`, `routing`, `tools`, `escalation`, `audit`.
- Frontend has a dedicated `admin/chatbot` area.
- Architecture docs reference the implementation plan.

