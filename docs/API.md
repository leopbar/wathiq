# Wathiq API contract (v1)

This file is the agreement between `backend/` (FastAPI) and `frontend/` (React).
Base URL: `/api/v1`. The frontend dev server proxies `/api` → `http://api:8000`.
Auth: `Authorization: Bearer <jwt>`. Token stored in `localStorage` under `wathiq.token`.

**Browser-initiated GETs.** Three endpoints also accept the token as a `?token=` query parameter,
because an `<iframe src>`, an `EventSource` and a download link cannot set a header:
`GET /documents/{id}/file`, `GET /cases/{id}/events`, `GET /audit/export`.
No other endpoint accepts it — a token in the URL can never change anything (see
[DECISIONS.md #21](DECISIONS.md)).

## Enums

```ts
type Role = "ops_officer" | "reviewer" | "supervisor" | "admin" | "auditor";

type CaseStatus =
  | "intake" | "processing" | "needs_review" | "in_review"
  | "approved" | "posting" | "completed" | "rejected" | "failed";

type CaseType = "kyc_refresh" | "salary_certificate";
type Severity = "info" | "warning" | "critical";
type FieldStatus = "auto_accepted" | "needs_review" | "corrected" | "rejected";
type ReviewDecision = "approve" | "correct" | "reject" | "escalate";
type DocTypeKey =
  | "trade_license" | "emirates_id" | "passport" | "moa"
  | "salary_certificate" | "unknown";
type IntegrationStatus = "connected" | "simulated" | "demo" | "disabled";
type ActorType = "user" | "agent" | "system";
```

## Shared shapes

```ts
interface User { id: string; email: string; full_name: string; full_name_ar: string;
  role: Role; is_active: boolean; }

interface Page<T> { items: T[]; total: number; page: number; size: number; pages: number; }

interface CaseSummary {
  id: string; reference: string;           // "WTQ-2026-0042"
  case_type: CaseType;
  customer_name: string; customer_name_ar: string;
  status: CaseStatus;
  risk_level: "low" | "medium" | "high";
  priority: "normal" | "high" | "urgent";
  confidence: number | null;               // 0..1 overall calibrated confidence
  document_count: number;
  finding_count: number;
  open_finding_count: number;
  straight_through: boolean;
  assigned_to: { id: string; full_name: string } | null;
  sla_due_at: string | null;               // ISO 8601
  sla_state: "on_track" | "at_risk" | "breached" | "none";
  created_at: string; updated_at: string; completed_at: string | null;
  processing_ms: number | null; cost_usd: number | null;
}

interface CaseDetail extends CaseSummary {
  thread_id: string;                       // == Conductor workflow id
  created_by: { id: string; full_name: string } | null;
  documents: Document[];
  fields: ExtractedField[];
  findings: Finding[];
  timeline: TimelineEvent[];
  review_tasks: ReviewTask[];
}

interface Document {
  id: string; case_id: string; filename: string;
  doc_type: DocTypeKey; doc_type_label: string;
  language: "en" | "ar" | "mixed";
  mime_type: string; size_bytes: number; page_count: number;
  ocr_confidence: number | null;           // 0..1
  classification_confidence: number | null;
  status: "uploaded" | "ocr" | "classified" | "extracted" | "failed";
  preview_url: string;                     // GET /api/v1/documents/{id}/file
  created_at: string;
}

interface ExtractedField {
  id: string; case_id: string; document_id: string | null;
  name: string;                            // snake_case key, e.g. "license_number"
  label_en: string; label_ar: string;
  value: string | null;                    // what the agent extracted
  corrected_value: string | null;          // what a reviewer typed
  confidence: number;                      // raw 0..1
  calibrated_confidence: number;           // 0..1 after calibration
  status: FieldStatus;
  is_critical: boolean;
  page: number | null;
  bbox: [number, number, number, number] | null;  // normalised x,y,w,h in 0..1
  source_text: string | null;              // grounding snippet
}

interface Finding {
  id: string; case_id: string; code: string;      // "CROSS_DOC_NAME_MISMATCH"
  severity: Severity; title: string; description: string;
  policy_citation: string | null;                 // "KYC-POL-004 §3.2"
  policy_quote: string | null;
  status: "open" | "resolved" | "waived";
  created_at: string;
}

interface TimelineEvent {
  id: string; case_id: string;
  actor: string;                           // "supervisor_node" | user full name | "system"
  actor_type: ActorType;
  action: string;                          // "document.classified"
  label: string;                           // human sentence for the UI
  detail: Record<string, unknown> | null;
  prompt_version: string | null;           // "kyc_extract@2.1.0"
  model_version: string | null;            // "fake-model-1" | "gpt-4.1-mini"
  duration_ms: number | null;
  created_at: string;
}

interface ReviewTask {
  id: string; case_id: string; case_reference: string;
  customer_name: string;
  reason: "mandatory" | "dynamic";
  reason_code: string;                     // "SANCTIONS_POSSIBLE_MATCH"
  reason_label: string;
  status: "pending" | "in_progress" | "completed";
  assigned_role: Role;
  assigned_to: { id: string; full_name: string } | null;
  sla_due_at: string | null;
  sla_state: "on_track" | "at_risk" | "breached" | "none";
  decision: ReviewDecision | null;
  decision_reason_code: string | null;
  decision_note: string | null;
  created_at: string; completed_at: string | null;
  field_count: number; open_finding_count: number;
}
```

## Endpoints

### Auth
| Method | Path | Body / Query | Returns |
|---|---|---|---|
| POST | `/auth/login` | `{email, password}` | `{access_token, token_type:"bearer", user: User}` |
| GET | `/auth/me` | — | `User` |
| GET | `/auth/demo-users` | — | `DemoUser[]` (demo mode only, no auth) |
| POST | `/auth/demo-login` | `{role: Role}` | same as login (demo mode only) |

`DemoUser = { role, email, full_name, title, description }` — used for the one-click cards on Login.
If mode is `azure`, `/auth/demo-users` returns `[]` and `/auth/demo-login` returns 404.

### Cases
| Method | Path | Notes |
|---|---|---|
| GET | `/cases` | query: `status` (repeatable), `case_type`, `q`, `assigned_to_me`, `sla_state`, `page=1`, `size=20`, `sort=-created_at` → `Page<CaseSummary>` |
| GET | `/cases/{id}` | `CaseDetail` |
| POST | `/cases` | `{customer_name, customer_name_ar?, case_type, priority?, notes?}` → `CaseDetail` |
| POST | `/cases/{id}/documents` | multipart `files[]` → `Document[]` |
| POST | `/cases/{id}/start` | begins the pipeline → `{thread_id, status}` |
| GET | `/cases/{id}/events` | **SSE** stream, `event: progress` with `{node, status, message, percent, timeline_event?}` (M2; in M1 it emits a heartbeat then `event: done`) |
| GET | `/documents/{id}/file` | raw PDF/PNG bytes |

### Review
| Method | Path | Notes |
|---|---|---|
| GET | `/review/queue` | query: `mine`, `status`, `sla_state`, `page`, `size` → `Page<ReviewTask>` |
| GET | `/review/tasks/{id}` | `{task: ReviewTask, case: CaseDetail}` |
| POST | `/review/tasks/{id}/claim` | → `ReviewTask` |
| POST | `/review/tasks/{id}/decision` | `{decision, reason_code?, note?, field_corrections?: {field_id, value}[]}` → `ReviewTask` |
| GET | `/review/reason-codes` | → `{code, label, applies_to: ReviewDecision[]}[]` |

### Dashboard
`GET /dashboard/kpis` →
```ts
{ cases_today: number; cases_total: number; straight_through_rate: number;  // 0..1
  review_rate: number; avg_handling_ms: number; sla_breaches: number;
  avg_cost_usd: number; open_reviews: number; deltas: Record<string, number>; }
```
`GET /dashboard/charts` →
```ts
{ volume_by_day: { date: string; total: number; straight_through: number; reviewed: number }[];
  status_split: { status: CaseStatus; count: number }[];
  confidence_histogram: { bucket: string; count: number }[];
  handling_time_by_day: { date: string; p50_ms: number; p90_ms: number }[];
  top_findings: { code: string; title: string; count: number }[]; }
```

### Quality Lab (M1: seeded read-only)
`GET /quality/summary` → `{ bands: { band: string; label: string; passed: number; failed: number; total: number; score: number; last_run_at: string }[]; overall_score: number; }`
`GET /quality/runs?band=` → `Page<{ id; band; started_at; finished_at; passed; failed; score; triggered_by; commit_sha }>`
`GET /quality/runs/{id}` → `{ run, cases: { id; name; band; status:"passed"|"failed"; expected; actual; note }[] }`
`GET /quality/calibration` → `{ points: { predicted: number; observed: number; n: number }[]; ece: number; brier: number }`
`POST /quality/runs` → `{ band: QualityBand | "all" }` starts a run; `"all"` (the default) runs every
band. M1 returns the most recent seeded run instead of starting a real evaluation.

### Prompt Studio (M1: seeded read-only)
`GET /prompts` → `{ id; key; name; latest_version; status; document_type; updated_at; versions_count }[]`
`GET /prompts/{key}/versions` → `{ id; version; status:"draft"|"approved"|"retired"; body; notes; created_by; created_at; approved_by; approved_at; eval_score: number|null }[]`
`GET /prompts/{key}/diff?from=&to=` → `{ from, to, unified_diff: string }`
`POST /prompts/{key}/versions/{version}/approve` → version (admin only)
`POST /prompts/{key}/versions/{version}/retire` → version (admin only)

### Settings
`GET /settings/document-types` → `{ id; key; name_en; name_ar; version; fields: {name,label_en,label_ar,type,required,is_critical}[]; rules_count; is_active }[]`
`GET /settings/integrations` → `{ key; name; category; status: IntegrationStatus; detail: string; docs_url?: string }[]`
`GET /settings/users` → `User[]` (admin only)
`GET /settings/mode` → `{ mode: "demo" | "azure"; version: string; features: Record<string, boolean> }` — **no auth required**

### Audit
`GET /audit` → query `q, actor, action, case_id, date_from, date_to, page, size` → `Page<AuditEntry>`
```ts
interface AuditEntry { id: string; case_id: string | null; case_reference: string | null;
  actor: string; actor_type: ActorType; action: string; label: string;
  detail: Record<string, unknown> | null; prompt_version: string | null;
  model_version: string | null; ip_address: string | null; created_at: string; }
```
`GET /audit/export?format=csv` → CSV file download.

### System (About screen)
`GET /system/info` →
```ts
{ mode: "demo"|"azure"; version: string; build_sha: string; started_at: string;
  stack: { layer: string; items: { name; version; why: string; alternative: string }[] }[];
  services: { name; status: "healthy"|"degraded"|"down"|"disabled"; detail: string }[];
  diagrams: { key: string; title: string; mermaid: string }[]; }
```
`GET /system/graph` → `{ mermaid: string }` (live LangGraph `draw_mermaid`, M2+; M1 returns the planned graph)
`GET /healthz` (no prefix) → `{status:"ok", db:"ok", mode}`

## Errors
All errors: HTTP status + `{ "detail": "<human message>", "code": "<MACHINE_CODE>" }`.
401 → frontend clears the token and redirects to `/login`. 403 → "not allowed for your role" screen.

## Role access (enforced server-side, mirrored in the UI)
| Screen | ops_officer | reviewer | supervisor | admin | auditor |
|---|---|---|---|---|---|
| Dashboard | ✅ own | ✅ queue view | ✅ team view | ✅ | ✅ read |
| New case | ✅ | — | ✅ | ✅ | — |
| Cases / detail | ✅ | ✅ | ✅ | ✅ | ✅ read |
| Review workspace | — | ✅ | ✅ | ✅ | — |
| Quality Lab | — | ✅ read | ✅ | ✅ | ✅ read |
| Prompt Studio | — | — | ✅ read | ✅ | ✅ read |
| Settings | — | — | ✅ read | ✅ | ✅ read |
| Audit log | ✅ own cases | ✅ | ✅ | ✅ | ✅ |
| About | everyone | | | | |
