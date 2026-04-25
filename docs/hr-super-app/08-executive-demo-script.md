# Executive Demo Script

## Audience

Top management, HR leadership, IT leadership.

## Duration

10-12 minutes.

## Demo Goal

Show that WinLab HR Super-App is not just a chatbot. It is an HR operating platform with:

- employee self-service;
- onboarding automation;
- knowledge governance;
- 1C integration through secure tools;
- HR analytics and escalation management.

## Talk Track

### 1. Business Problem

Employees need HR answers quickly. HR teams spend time answering repeated questions. New hires need structured adaptation. Management needs visibility into adaptation progress, employee questions, and bottlenecks.

### 2. Proposed Experience

Open `demo/executive-demo.html`.

Show the employee chat:

1. Employee asks about vacation balance.
2. Chatbot routes this as HR self-service.
3. Runtime calls backend tool, not 1C directly from LLM.
4. Response is returned with audit and access control.

Then show onboarding:

1. Employee asks about adaptation plan.
2. Runtime routes request to onboarding module.
3. Employee sees next step and accountable owner.

### 3. Architecture Confidence

Explain the separation:

- Channel Gateway normalizes Web/Yandex/Mobile.
- Chatbot Runtime owns conversation state, intent routing, consent, escalation.
- AI/RAG answers only from approved knowledge sources.
- HR tools call 1C through Integration Gateway.
- Audit records all sensitive actions.

### 4. Management Value

Expected outcomes:

- reduce repeated HR questions;
- reduce adaptation blind spots;
- improve employee satisfaction;
- increase transparency for HR and managers;
- create reusable platform for surveys, documents, and analytics.

### 5. Implementation Roadmap

Recommended sequence:

1. Chatbot Runtime + RAG MVP.
2. Onboarding journeys.
3. Preboarding documents.
4. 1C self-service tools.
5. Surveys + analytics.

## Questions To Prepare For

### Is this safe for payroll and personal data?

Yes. LLM does not directly access 1C. It calls typed backend tools with RBAC/ABAC checks, PII scope policy, and audit logging.

### Can it work in Yandex Messenger?

Yes. The architecture includes Channel Gateway and a Yandex adapter. The same runtime can later support Web, Telegram, and mobile channels.

### What do we reuse from ai-recruiter?

We reuse chat/session patterns, OpenAI integration, admin UX patterns, and transcript/reporting experience. We do not reuse interview-specific business logic directly.

### What is the first production MVP?

Yandex/Web chatbot, approved knowledge base, unresolved questions with consent escalation, and basic onboarding guidance.

