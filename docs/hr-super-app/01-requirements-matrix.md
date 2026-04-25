# WinLab HR Super-App Requirements Matrix

## Scope

This matrix maps WinLab product requirements to concrete platform capabilities and identifies what can be reused from the existing `ai-recruiter` codebase.

## Requirement Coverage Matrix

| Requirement Area | Business Requirement | Target Capability | Reuse from ai-recruiter | Gap / New Build |
|---|---|---|---|---|
| Onboarding / Adaptation | New hire adaptation in first days/weeks/month | Onboarding plans, checklists, milestones, reminders, owner assignments | Admin panel patterns, roles, status tracking | New `onboarding` domain, task engine, timeline views |
| Preboarding | Security questionnaire and hiring document collection | Preboarding forms + document workflow + approval statuses | Invite link flow, candidate profile bootstrap | Secure document vault, workflow states, compliance controls |
| Knowledge Base | Verified source of HR information | Content repository, approval workflow, searchable KB, source citations | Prompt tools, existing OpenAI integration | Full content lifecycle, chunking pipeline, relevance governance |
| HR Self-Service | Vacation balance, payroll calculation info, worked hours, certificates | Tool-based transactional queries through backend | Auth/RBAC baseline, chat UI patterns | 1C integration gateway, policy checks per data type |
| Analytics | Adaptation progress by city/department/stage | Operational dashboards and periodic aggregates | Existing reports/PDF pipeline | Data marts, cross-module KPIs, event instrumentation |
| Surveys / Exit | Pulse surveys and exit interviews | Survey templates, scheduled campaigns, feedback analytics | Candidate/session/report objects partially reusable | Survey engine, scheduler, sentiment/aggregation layer |
| Channels | Yandex Messenger and web channels | Channel adapter abstraction + omnichannel conversation router | Existing web UI + chat backend | Yandex adapter + unified channel session mapping |
| Security / Compliance | Correct, timely, role-safe delivery of HR data | ABAC/RBAC, audit log, consent flows, PII policies | JWT, basic RBAC (`admin`, `superadmin`, `candidate`) | Fine-grained policy engine, immutable audit stream |
| Escalation | Unknown intents should be confirmed and routed to admin | Unresolved query queue + consented escalation | Existing chat/error handling | New `UnresolvedQuery`, assignment queue, SLA controls |

## Non-Functional Requirements

| NFR | Target |
|---|---|
| Reliability | Business-critical self-service APIs >= 99.5% monthly availability |
| Performance | FAQ answers <= 3s p95, transactional HR queries <= 5s p95 |
| Security | Encrypted data at rest/in transit, role-based access and audit for all PII actions |
| Scalability | Horizontal API scaling, async workers for document ingestion and integrations |
| Operability | Centralized logs, metrics, traces, per-integration health dashboards |

## Requirement Prioritization

1. Channel + identity foundation (web + Yandex, auth, role model)
2. Knowledge + RAG (verified answers only)
3. Onboarding/adaptation workflows
4. 1C integration for high-value self-service endpoints
5. Preboarding documents and surveys
6. Advanced analytics and additional channel adapters

