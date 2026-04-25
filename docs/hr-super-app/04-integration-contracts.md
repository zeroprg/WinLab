# WinLab HR Super-App Integration Contracts

## Integration Principles

- All external calls go through an integration boundary (`Integration Gateway`).
- LLM never accesses external systems directly.
- Every integration operation has audit, retry policy, and idempotency key.

## 1C Contract (HRIS / Payroll source)

## Sync Endpoints (Gateway -> HR Core)

| Operation | Method | Contract |
|---|---|---|
| Employee snapshot sync | `POST /integrations/1c/sync/employees` | Upsert employee identity and org links |
| Department sync | `POST /integrations/1c/sync/departments` | Upsert department tree |
| Position sync | `POST /integrations/1c/sync/positions` | Upsert position references |
| Incremental checkpoint update | `POST /integrations/1c/checkpoints` | Persist integration cursor |

### Query Tool Contracts (HR Core -> Gateway)

| Tool Name | Input | Output | Access Policy |
|---|---|---|---|
| `getVacationBalance` | `employee_id` | remaining days, accrual date | employee/self + hr_admin |
| `getWorkedHours` | `employee_id`, `period` | worked, overtime, missing hours | employee/self + manager + hr_admin |
| `getPayrollSummary` | `employee_id`, `period` | gross/net components | employee/self + hr_admin (restricted) |
| `requestCertificate` | `employee_id`, `certificate_type` | request id, SLA | employee/self |

### Error Envelope

```json
{
  "success": false,
  "error_code": "UPSTREAM_TIMEOUT",
  "message": "1C did not respond within timeout",
  "retryable": true,
  "correlation_id": "req_123"
}
```

## Yandex Messenger Contract

## Channel Adapter Interface

| Capability | Contract |
|---|---|
| Receive message | `POST /channels/yandex/events` |
| Send text reply | `POST /channels/yandex/send` |
| Send button set | `POST /channels/yandex/send-actions` |
| Attach file link | `POST /channels/yandex/send-file` |
| Resolve identity | `POST /channels/yandex/resolve-user` |

### Canonical Event Payload

```json
{
  "channel": "yandex_messenger",
  "external_user_id": "ym_123",
  "session_external_id": "chat_456",
  "message_id": "msg_789",
  "text": "Сколько дней отпуска осталось?",
  "timestamp": "2026-04-25T08:00:00Z"
}
```

### Mapping Rule

- `external_user_id` maps to `ExternalIdentityMap`.
- Missing mapping triggers controlled registration flow (link/QR-based).

## Sber Pulse Contract (future-safe)

## Event Export Contract

| Event | Payload |
|---|---|
| `survey.completed` | respondent metadata, template id, score bundle |
| `onboarding.stage_completed` | employee id, stage, completion timestamp |
| `unresolved_query.created` | intent class, confidence, escalation target |

### Delivery Semantics

- At-least-once delivery with dedup key `event_id`.
- Consumer acknowledgment required within timeout.
- Dead-letter queue for poison events.

## Security and Compliance Contract

1. Signed integration requests (`X-Signature`, `X-Timestamp`)
2. Correlation ID propagation (`X-Correlation-ID`)
3. PII scope tag in each request (`pii_scope`: `none`, `basic_hr`, `sensitive_hr`)
4. Mandatory audit event for all read/write operations involving payroll, hours, and security forms

