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
  // What the confidence was built from (M3). Null on cases seeded before it existed.
  signals: { key: "ocr"|"grounded"|"label"|"shape"|"critic";
             label: string; value: number; weight: number; detail: string }[] | null;
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
| GET | `/auth/config` | — | `{backend, demo_accounts_available, entra:{...}}` — **no auth**; the login screen reads it to decide which sign-in methods to offer. A tenant id and a client id are public identifiers; no secret is included |
| GET | `/auth/demo-users` | — | `DemoUser[]` (local demo auth only, no auth) |
| POST | `/auth/demo-login` | `{role: Role}` | same as login (local demo auth only) |

`DemoUser = { role, email, full_name, title, description }` — used for the one-click cards on Login.
Provider mode and authentication are independent. An Azure-service deployment may use
`WATHIQ_AUTH_BACKEND=demo` for a controlled demo before an Entra browser app registration exists.
With `WATHIQ_AUTH_BACKEND=entra`, `/auth/demo-users` returns `[]` and `/auth/demo-login` returns 404.

With `WATHIQ_AUTH_BACKEND=entra` every endpoint accepts a **Microsoft Entra ID** access token as
the bearer token instead of a Wathiq-issued one. It is validated against the tenant's JWKS
(RS256 only, audience, issuer, expiry), the app role in the token decides the Wathiq role, and a
user who has never signed in before is created on the spot. A token carrying no recognised Wathiq
app role is rejected rather than downgraded. (M6, DECISIONS #73)

### Cases
| Method | Path | Notes |
|---|---|---|
| GET | `/cases` | query: `status` (repeatable), `case_type`, `q`, `assigned_to_me`, `sla_state`, `page=1`, `size=20`, `sort=-created_at` → `Page<CaseSummary>` |
| GET | `/cases/{id}` | `CaseDetail` |
| POST | `/cases` | `{customer_name, customer_name_ar?, case_type, priority?, notes?}` → `CaseDetail` |
| POST | `/cases/{id}/documents` | multipart `files[]` → `Document[]` |
| POST | `/cases/{id}/start` | begins the pipeline → `{thread_id, status}` |
| GET | `/cases/{id}/events` | **SSE** stream, `event: progress` with `{node, status, message, percent, timeline_event?}` (M2; in M1 it emits a heartbeat then `event: done`) |
| GET | `/cases/{id}/assurance` | the evidence behind the case, read from the agent's checkpoint (M3) |
| GET | `/documents/{id}/file` | raw PDF/PNG bytes |

`GET /cases/{id}/assurance` →
```ts
{ available: boolean;   // false for a seeded case that never ran through the graph
  note: string;         // says why, when available is false
  thread_id: string;
  guardrails: { document_id; filename; blocked; sanitised; pii_counts: Record<string, number>;
                injection: { attacked; risk; engine; signals: {kind; pattern; excerpt}[] };
                safety: { flagged; severities: Record<string, number>; matches: string[] } }[];
  worker_results: { document_id; filename; doc_type; field_count; attempts; validated;
                    duration_ms; model_version; prompt_version;
                    repairs: {field; pass; strategy; error; explanation; before; after}[];
                    examples: {id; doc_type; note; similarity}[] }[];
  critic_notes: { field; agreed; reason; via; suggested_value }[];
  investigation: { index; thought; action; action_input; observation; ok; duration_ms }[];
  tool_calls: { server; tool; arguments; ok; duration_ms; result; error }[];
  plan: { document_id; filename; doc_type; classification_confidence; evidence: string[];
          field_count; dispatched; skipped_because; prompt_version }[];
  rule_packs: Record<string, string>;      // doc type -> "trade_license@1.2.0"
  prompt_versions: Record<string, string>;
  calibration: CalibrationCurve;
  review_reasons: { code; label }[]; }
```

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

### Quality Lab (M5: measured evaluations)
`GET /quality/summary` → `{ bands: { band: string; label: string; passed: number; failed: number; total: number; score: number; last_run_at: string }[]; overall_score: number; }`
`GET /quality/runs?band=` → `Page<{ id; band; started_at; finished_at; passed; failed; score; triggered_by; commit_sha }>`
`GET /quality/runs/{id}` → `{ run, cases: { id; name; band; passed:boolean; expected; actual; note; is_regression }[] }`
`GET /quality/calibration` →
```ts
{ points: { predicted: number; observed: number; n: number }[];
  ece: number; brier: number; model_version: string;
  curve: { a; b; fitted: boolean; sample_count; brier_before; brier_after; improvement;
           model_version };   // fitted=false means the product is showing raw scores
  method: string; ground_truth: string; }
```
`POST /quality/calibration/refit` → the same shape. Fits the curve again on every field a reviewer
has decided (accepted = the extractor was right, corrected = it was wrong). Refuses to fit on too
little data, or when the fit would score worse than the raw numbers. Admin and supervisor only.
`POST /quality/runs` → `{ band: QualityBand | "all" }` starts a run; `"all"` (the default) runs every
band. Returns `{ runs: QualityRun[] }` after completion; all five produces five records.
Each run includes `provenance` (dataset, model, sample count, scope and optional prompt identity).
The summary excludes illustrative seed data and counts permanent regression examples separately.
`GET /quality/dataset` → authenticated ZIP with 50 PDFs and answer keys.
`GET /quality/regressions/export` → synthetic correction snapshots for the checked-in CI fixture.
Calibration also returns `sample_count`, `metric_scope` and MLflow `tracking` status.

### Prompt Studio
`GET /prompts` → `{ id; key; name; latest_version; status; document_type; updated_at; versions_count }[]`
`GET /prompts/{key}/versions` → `{ id; version; status:"draft"|"approved"|"retired"; body; notes; created_by; created_at; approved_by; approved_at; eval_score: number|null }[]`
`GET /prompts/{key}/diff?from=&to=` → `{ from, to, unified_diff: string }`
`POST /prompts/{key}/versions/{version}/approve` → version (admin only)
`POST /prompts/{key}/versions/{version}/retire` → version (admin only)
`POST /prompts/{key}/versions/{version}/evaluate` → `{ runs: QualityRun[] }` (admin, supervisor, reviewer).
`GET /prompts/{key}/versions/{version}/evaluations` → measured history for that version.
Live wording sensitivity is unsupported by the demo reader; see [QUALITY.md](QUALITY.md).

### Settings
`GET /settings/document-types` → `{ id; key; name_en; name_ar; version; fields: {name,label_en,label_ar,type,required,is_critical}[]; rules_count; is_active }[]`
`GET /settings/integrations` → `{ key; name; category; status: IntegrationStatus; detail: string; docs_url?: string }[]`
`GET /settings/users` → `User[]` (admin only)
`GET /settings/mode` → `{ mode: "demo" | "azure"; version: string; features: Record<string, boolean> }` — **no auth required**. `features.azure_services` counts services that are *actually* configured, not merely the mode.

`GET /settings/azure` → which Azure services this deployment uses, service by service (M6):
```
{ mode, auth_backend,
  services: { key, name, enabled, endpoint, detail, replaces }[],
  credential: "Managed identity (Entra)" | "API key",
  tracing_enabled: boolean }
```
Generated from the running settings, so it cannot claim a service that is switched off. `replaces` names what runs instead when one is not configured — the honest half of the story. No key or connection string is ever included.
`GET /settings/assurance` → how the agent assures its answers, generated from the running code:
```ts
{ guardrails: { key; name; purpose; implementation; azure }[];
  confidence_signals: { key; label; weight }[];
  tool_servers: { key; name; url_configured; can_write; tools: string[];
                  used_by_nodes: string[] }[];     // the least-privilege matrix
  rule_packs: { id; version; title; description; applies_to: string[]; source;
                rules: { id; severity; message; policy; explain; expr; check }[] }[];
  registered_checks: string[];
  graph_steps: { key; label }[];
  policy_documents: { name; sections: number }[];
  embedder: string;
  calibration: CalibrationCurve; }
```

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
`GET /system/case-types` → the case-type profiles the engine reads (M7), signed-in users only:
```ts
{ id: CaseType; version: string; title_en: string; title_ar: string;
  customer_kind: "corporate"|"individual";
  expected_documents: { key: DocTypeKey; label_en: string; label_ar: string }[];
  posting_tool: string; posting_record: string; registry_checks: string[] }[]
```

### Failure-mode gallery (M7)
`GET /failure-gallery` → every scenario: `{ id, category, title_en/ar, problem_en/ar,
detection_en/ar, outcome_en/ar, where_to_look_en/ar, runnable: boolean, case_type, customer_name,
expected_codes: string[], files: { filename, doc_type }[], evidence: string[] }[]`.
`GET /failure-gallery/{id}/files/{index}` → the scenario's synthetic PDF. There is deliberately
no "run" endpoint: the browser sends these files through `POST /cases`, `/documents` and `/start`
like any upload.
`GET /healthz` (no prefix) → `{status:"ok"|"degraded", db:"ok"|"down", mode, version}` — **liveness**. Always 200 while the process can answer. It reports the database as a fact and deliberately does not fail on it: a liveness probe that fails on an unreachable database restarts the API in a loop for something restarting cannot fix, killing every case mid-run.

`GET /readyz` (no prefix) → `{status:"ready"|"not-ready", db, mode, version}` — **readiness**, and it returns **503** when the database is unreachable. That is the whole difference: readiness decides whether this instance is in the load balancer, liveness decides whether it is killed. (M6, for the AKS deployment.)

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

## Process layer (M4)
`GET /process/health` → which engine is running the business process, and whether Conductor answers
```ts
{ configured: "auto"|"conductor"|"inprocess"; active: string; fell_back: boolean;
  engines: { engine; reachable: boolean; detail: string; workflow_registered: boolean; url: string }[];
  process: { workflow: string; version: number; sla_hours: number; worker_queues: string[];
             steps: { ref; kind; label; description; queue; writes_externally; only_on_route }[];
             mermaid: string } }
```
`GET /process/definition` → the workflow as the code declares it (the `process` object above)
`POST /process/sla/sweep` → run the SLA check now; supervisor or admin only
```ts
{ escalated: number; note: string }
```
It escalates only reviews that are already past their SLA and have not been escalated before, so it
cannot manufacture an escalation.

`GET /process/audit-integrity` → whether the database is enforcing append-only on the audit trail
```ts
{ append_only_enforced: boolean; trigger: string; detail: string; rows: number;
  first_seq: number|null; last_seq: number|null; oldest: string|null; newest: string|null;
  limits: string }
```
`limits` states what the check does *not* prove. It is part of the response, not a footnote.

`GET /cases/{id}/process` → where one case is in the business process
```ts
{ engine: string; workflow_name: string; workflow_version: number; workflow_id: string;
  route: "review"|"straight_through"|""; escalated: boolean; started: boolean; finished: boolean;
  steps: { ref; label; kind; status: "pending"|"running"|"waiting"|"completed"|"skipped"|"failed";
           at: string|null; detail: string; writes_externally: boolean }[];
  posting: { status: "posted"|"skipped"|"failed"; reference: string|null; customer_id: string;
             approval_kind: "human"|"straight_through_policy"|""; approved_by: string;
             duplicate: boolean; idempotency_key: string; note: string; posted_at: string|null;
             simulated: true } | null;
  live: { workflow_id; status; start_time; end_time;
          tasks: { ref; type; status; retried }[] } | null;
  posting_reference: string|null; note: string }
```
The steps are derived from the case's own append-only event log, so this view and the audit trail
cannot disagree. `live` is Conductor's own record of the instance, present only when Conductor ran
the case and answered.

### Statuses a case moves through
`intake → processing → [needs_review → in_review] → approved → posting → completed`, or `rejected`
or `failed`. **`completed` means posted and sealed**, not "the graph finished" — the audit step is
the only thing that writes it.

### New error code
`503 SERVICE_UNAVAILABLE` / `CONDUCTOR_UNAVAILABLE` — the orchestrator could not be reached. On a
review decision it means the decision *was* recorded and the case has not moved on yet; a reviewer's
judgement is never discarded because an orchestrator hiccupped.
