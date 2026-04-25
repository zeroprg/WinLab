# WinLab HR Super-App Modularization Blueprint

## Current State (to preserve)

The current codebase already provides a stable recruiting backbone:

- Backend: `server/routes`, `server/models`, `server/services`
- Frontend admin: `User Interface/my-chat-react/src/components/admin/RecruitingAdmin.tsx`
- Realtime/chat layer: `server/server.py`, `InterviewPage.tsx`, chat hooks

## Target Module Layout

```text
server/
  modules/
    identity/
    recruiting/
    onboarding/
    preboarding/
    chatbot/
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

## Backend Refactor Phases

### Phase A: Packaging without behavior changes

- Move existing recruiting routers into `server/modules/recruiting/routes/`:
  - `positions.py`
  - `interviewees.py`
  - `invites.py`
  - `reports.py`
  - recruiting-related parts of `assessments.py`
- Keep existing route paths unchanged (`/api/...`) via compatibility imports.

### Phase B: Service isolation

- Extract bounded services:
  - `prompt_resolver.py` -> `modules/recruiting/services/prompt_resolver.py`
  - `assessment_service.py` -> `modules/recruiting/services/assessment_service.py`
  - `report_pdf.py` -> `modules/recruiting/services/report_pdf.py`
- Introduce `modules/shared/events` for async domain events.
- Extract reusable chat foundation from the existing `ai-recruiter` chat/realtime code:
  - `ChatSession`
  - `ChatMessage`
  - `ChatParticipant`
  - `ChatChannel`
- Keep recruiting behavior unchanged through a `RecruitingBotPolicy` adapter.

### Phase C: New domain modules

- Add new modules with minimal skeleton APIs:
  - `chatbot`
  - `onboarding`
  - `preboarding`
  - `knowledge`
  - `surveys`
  - `integrations`
- Keep each module with explicit `models`, `routes`, `services`, `schemas`.

### Chatbot Module Layout

```text
server/modules/chatbot/
  channels/
    yandex.py
    web.py
    telegram.py
  conversation/
    state.py
    repository.py
  routing/
    intent_router.py
    policies.py
  tools/
    executor.py
    registry.py
  escalation/
    service.py
  audit/
    events.py
  schemas.py
  routes.py
```

The `chatbot` module orchestrates channels, conversation state, intent routing, RAG calls, HR tools, escalation, and audit. It must not own 1C, onboarding, surveys, or knowledge business logic directly.

## Frontend Modularization

## Current Issue

`RecruitingAdmin.tsx` is overloaded with multiple responsibilities.

## Target Split

```text
src/components/admin/
  recruiting/
    RecruitingDashboard.tsx
    PositionsPanel.tsx
    CandidatesPanel.tsx
    ReportsPanel.tsx
  onboarding/
    OnboardingAdmin.tsx
  preboarding/
    PreboardingAdmin.tsx
  chatbot/
    ChatbotDashboard.tsx
    UnresolvedQueriesPanel.tsx
    ConversationLogsPanel.tsx
    ChannelSettingsPanel.tsx
    BotPoliciesPanel.tsx
  knowledge/
    KnowledgeAdmin.tsx
  surveys/
    SurveysAdmin.tsx
```

## Reuse Matrix

| Existing Component | Action | Why |
|---|---|---|
| `server/models/position.py` | Reuse + extend | Core recruiting primitive |
| `server/models/interviewee.py` | Reuse | Candidate lifecycle stays valid |
| `server/models/interview_session.py` | Reuse + metadata extension | Session analytics and channel routing |
| `server/routes/auth.py` + `middleware/auth.py` | Reuse first, later harden | MVP speed with upgrade path to enterprise identity |
| `server/services/openai_client.py` | Reuse | Common AI gateway for recruiting + HR bot |
| Existing chat hooks / web chat UX | Reuse + adapt | Foundation for WinLab web chatbot channel |
| Existing message/session lifecycle | Reuse as pattern | Basis for `ConversationSession` and `ConversationMessage` |
| Existing realtime voice/text patterns | Reuse selectively | Optional future voice channel support |
| `RecruitingAdmin.tsx` | Split | Maintainability and team parallelism |

## Chatbot Policy Separation

The runtime foundation can be shared, but domain policies must stay separate:

| Policy | Scope |
|---|---|
| `RecruitingBotPolicy` | Interviews, vacancies, candidate assessment, PDF reports |
| `HrAssistantBotPolicy` | HR FAQ, onboarding, documents, 1C tools, surveys, escalation |

This prevents recruiting interview logic from leaking into employee HR self-service flows.

## Migration Safety Rules

1. API path compatibility first, package moves second.
2. One module extraction per PR to reduce regression risk.
3. Keep Alembic as single schema source of truth; avoid runtime schema mutations.
4. Add module contract tests before moving to full domain isolation.

