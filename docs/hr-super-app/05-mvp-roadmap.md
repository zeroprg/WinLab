# WinLab HR Super-App MVP Roadmap

## Delivery Strategy

Build in vertical slices, each release adding real business value while preserving existing recruiting operations.

## Phase 0 - Foundation (2-3 weeks)

### Deliverables
- Architecture baseline approved
- Security model v1 (roles, audit requirements, PII classification)
- Technical skeleton for new modules (`onboarding`, `knowledge`, `integrations`, `surveys`)
- Observability baseline (logs/metrics/traces)

### Exit Criteria
- CI/CD for new modules is green
- Production-like environment available
- Integration stubs for 1C and Yandex channels pass contract tests

## Phase 1 - Adaptation Chatbot MVP (4-6 weeks)

### Deliverables
- Knowledge base ingestion and RAG answers with source citations
- Yandex Messenger + Web channel adapter
- Employee registration via link/QR
- Unresolved query flow with user consent before escalation
- Admin content management for KB articles and FAQs

### KPIs
- FAQ deflection rate >= 40%
- Median answer time <= 3 seconds
- Escalation confirmation captured for 100% unresolved routes

## Phase 2 - Onboarding Journeys (4-5 weeks)

### Deliverables
- Onboarding plans (`day1`, `week1`, `month1`)
- Tasks/checklists with owners and due dates
- Progress dashboard by department/city
- Reminder notifications

### KPIs
- Onboarding plan completion rate visibility >= 95%
- Overdue task detection latency < 15 minutes

## Phase 3 - Preboarding and Documents (4-6 weeks)

### Deliverables
- Security questionnaire flow
- Document upload and review pipeline
- Status transitions (`draft -> submitted -> review -> approved/rejected`)
- Secure object storage references and audit logs

### KPIs
- 100% document actions auditable
- Average preboarding cycle time measurable per location

## Phase 4 - 1C Self-Service Integrations (5-7 weeks)

### Deliverables
- Vacation balance and worked hours tools
- Payroll summary access under strict policy
- Certificate request flow
- Retry/circuit breaker and integration health dashboard

### KPIs
- 1C query success rate >= 98%
- p95 transactional response <= 5 seconds
- Zero unauthorized access incidents to sensitive HR data

## Phase 5 - Surveys and Analytics Expansion (3-4 weeks)

### Deliverables
- Pulse and exit survey campaigns
- Analytics dashboards: onboarding progress, unresolved topics, HR load, recruiting funnel
- Export API for HR reporting

### KPIs
- Survey completion rate tracking by segment
- Weekly management dashboard auto-refresh

## Team Topology (recommended)

- 1 Platform/API squad (core, auth, shared infra)
- 1 Conversational AI squad (RAG, bot orchestration, unresolved intent handling)
- 1 HR Product squad (onboarding, preboarding, surveys, admin UX)
- 1 Integration squad (1C, Yandex, external adapters)
- Shared QA/DevOps/Security support

## Critical Risks and Mitigations

| Risk | Mitigation |
|---|---|
| 1C API constraints discovered late | Contract-first integration and early sandbox validation |
| Sensitive HR data leakage | ABAC policies, field-level masking, immutable audit log |
| Scope blow-up in first release | Enforce MVP boundaries and defer non-critical channels |
| Legacy module coupling slows delivery | Module boundary tests and phased extraction with compatibility routes |

