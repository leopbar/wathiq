/**
 * Transcribed from docs/API.md. Keep in sync with the backend contract.
 */

export type Role = "ops_officer" | "reviewer" | "supervisor" | "admin" | "auditor";

export type CaseStatus =
  | "intake"
  | "processing"
  | "needs_review"
  | "in_review"
  | "approved"
  | "posting"
  | "completed"
  | "rejected"
  | "failed";

export type CaseType = "kyc_refresh" | "salary_certificate";
export type Severity = "info" | "warning" | "critical";
export type FieldStatus = "auto_accepted" | "needs_review" | "corrected" | "rejected";
export type ReviewDecision = "approve" | "correct" | "reject" | "escalate";
export type DocTypeKey =
  | "trade_license"
  | "emirates_id"
  | "passport"
  | "moa"
  | "salary_certificate"
  | "unknown";
export type IntegrationStatus = "connected" | "simulated" | "demo" | "disabled";
export type ActorType = "user" | "agent" | "system";

export type RiskLevel = "low" | "medium" | "high";
export type Priority = "normal" | "high" | "urgent";
export type SlaState = "on_track" | "at_risk" | "breached" | "none";
export type AppMode = "demo" | "azure";

export interface User {
  id: string;
  email: string;
  full_name: string;
  full_name_ar: string;
  role: Role;
  is_active: boolean;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface UserRef {
  id: string;
  full_name: string;
}

export interface CaseSummary {
  id: string;
  reference: string; // "WTQ-2026-0042"
  case_type: CaseType;
  customer_name: string;
  customer_name_ar: string;
  status: CaseStatus;
  risk_level: RiskLevel;
  priority: Priority;
  confidence: number | null; // 0..1 overall calibrated confidence
  document_count: number;
  finding_count: number;
  open_finding_count: number;
  straight_through: boolean;
  assigned_to: UserRef | null;
  sla_due_at: string | null; // ISO 8601
  sla_state: SlaState;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  processing_ms: number | null;
  cost_usd: number | null;
}

export interface CaseDetail extends CaseSummary {
  thread_id: string; // == Conductor workflow id
  created_by: UserRef | null;
  documents: Document[];
  fields: ExtractedField[];
  findings: Finding[];
  timeline: TimelineEvent[];
  review_tasks: ReviewTask[];
}

export interface Document {
  id: string;
  case_id: string;
  filename: string;
  doc_type: DocTypeKey;
  doc_type_label: string;
  language: "en" | "ar" | "mixed";
  mime_type: string;
  size_bytes: number;
  page_count: number;
  ocr_confidence: number | null; // 0..1
  classification_confidence: number | null;
  status: "uploaded" | "ocr" | "classified" | "extracted" | "failed";
  preview_url: string; // GET /api/v1/documents/{id}/file
  created_at: string;
}

export interface ExtractedField {
  id: string;
  case_id: string;
  document_id: string | null;
  name: string; // snake_case key, e.g. "license_number"
  label_en: string;
  label_ar: string;
  value: string | null; // what the agent extracted
  corrected_value: string | null; // what a reviewer typed
  confidence: number; // raw 0..1
  calibrated_confidence: number; // 0..1 after calibration
  status: FieldStatus;
  is_critical: boolean;
  page: number | null;
  bbox: [number, number, number, number] | null; // normalised x,y,w,h in 0..1
  source_text: string | null; // grounding snippet
  /** What the confidence was built from. Null for cases seeded before M3. */
  signals: ConfidenceSignal[] | null;
}

/** One reason a field scored what it did. The UI shows these instead of a bare percentage. */
export interface ConfidenceSignal {
  key: "ocr" | "grounded" | "label" | "shape" | "critic";
  label: string;
  value: number; // 0..1, how strong this signal was
  weight: number; // 0..1, how much it counts
  detail: string; // plain English, e.g. "exact text found in the document"
}

export interface Finding {
  id: string;
  case_id: string;
  code: string; // "CROSS_DOC_NAME_MISMATCH"
  severity: Severity;
  title: string;
  description: string;
  policy_citation: string | null; // "KYC-POL-004 §3.2"
  policy_quote: string | null;
  status: "open" | "resolved" | "waived";
  created_at: string;
}

export interface TimelineEvent {
  id: string;
  case_id: string;
  actor: string; // "supervisor_node" | user full name | "system"
  actor_type: ActorType;
  action: string; // "document.classified"
  label: string; // human sentence for the UI
  detail: Record<string, unknown> | null;
  prompt_version: string | null; // "kyc_extract@2.1.0"
  model_version: string | null; // "fake-model-1" | "gpt-4.1-mini"
  duration_ms: number | null;
  created_at: string;
}

export interface ReviewTask {
  id: string;
  case_id: string;
  case_reference: string;
  customer_name: string;
  reason: "mandatory" | "dynamic";
  reason_code: string; // "SANCTIONS_POSSIBLE_MATCH"
  reason_label: string;
  status: "pending" | "in_progress" | "completed";
  assigned_role: Role;
  assigned_to: UserRef | null;
  sla_due_at: string | null;
  sla_state: SlaState;
  decision: ReviewDecision | null;
  decision_reason_code: string | null;
  decision_note: string | null;
  created_at: string;
  completed_at: string | null;
  field_count: number;
  open_finding_count: number;
}

/* ---------------------------------- auth ---------------------------------- */

export interface LoginResponse {
  access_token: string;
  token_type: "bearer";
  user: User;
}

export interface DemoUser {
  role: Role;
  email: string;
  full_name: string;
  title: string;
  description: string;
}

/* -------------------------------- dashboard ------------------------------- */

export interface DashboardKpis {
  cases_today: number;
  cases_total: number;
  straight_through_rate: number; // 0..1
  review_rate: number;
  avg_handling_ms: number;
  sla_breaches: number;
  avg_cost_usd: number;
  open_reviews: number;
  deltas: Record<string, number>;
}

export interface DashboardCharts {
  volume_by_day: { date: string; total: number; straight_through: number; reviewed: number }[];
  status_split: { status: CaseStatus; count: number }[];
  confidence_histogram: { bucket: string; count: number }[];
  handling_time_by_day: { date: string; p50_ms: number; p90_ms: number }[];
  top_findings: { code: string; title: string; count: number }[];
}

/* ---------------------------------- review -------------------------------- */

export interface ReviewTaskDetail {
  task: ReviewTask;
  case: CaseDetail;
}

export interface ReasonCode {
  code: string;
  label: string;
  applies_to: ReviewDecision[];
}

export interface FieldCorrection {
  field_id: string;
  value: string;
}

export interface ReviewDecisionPayload {
  decision: ReviewDecision;
  reason_code?: string;
  note?: string;
  field_corrections?: FieldCorrection[];
}

/* ------------------------------- quality lab ------------------------------ */

export interface QualityBand {
  band: string;
  label: string;
  passed: number;
  failed: number;
  total: number;
  score: number;
  last_run_at: string;
}

export interface QualitySummary {
  bands: QualityBand[];
  overall_score: number;
}

export interface QualityRun {
  id: string;
  band: string;
  started_at: string;
  finished_at: string | null;
  passed: number;
  failed: number;
  score: number;
  triggered_by: string;
  commit_sha: string;
}

export interface QualityRunCase {
  id: string;
  name: string;
  band: string;
  status: "passed" | "failed";
  expected: string;
  actual: string;
  note: string;
}

export interface QualityRunDetail {
  run: QualityRun;
  cases: QualityRunCase[];
}

export interface CalibrationCurve {
  a: number;
  b: number;
  fitted: boolean; // false = the numbers shown are raw, and the UI must say so
  sample_count: number;
  brier_before: number;
  brier_after: number;
  improvement: number;
  model_version: string;
}

export interface QualityCalibration {
  points: { predicted: number; observed: number; n: number }[];
  ece: number;
  brier: number;
  model_version: string;
  curve: CalibrationCurve;
  method: string;
  ground_truth: string;
}

/* ------------------------------ prompt studio ----------------------------- */

export type PromptStatus = "draft" | "approved" | "retired";

export interface PromptSummary {
  id: string;
  key: string;
  name: string;
  latest_version: string;
  status: PromptStatus;
  document_type: string;
  updated_at: string;
  versions_count: number;
}

export interface PromptVersion {
  id: string;
  version: string;
  status: PromptStatus;
  body: string;
  notes: string;
  created_by: string;
  created_at: string;
  approved_by: string | null;
  approved_at: string | null;
  eval_score: number | null;
}

export interface PromptDiff {
  from: string;
  to: string;
  unified_diff: string;
}

/* --------------------------------- settings ------------------------------- */

export interface DocumentTypeField {
  name: string;
  label_en: string;
  label_ar: string;
  type: string;
  required: boolean;
  is_critical: boolean;
}

export interface DocumentTypeConfig {
  id: string;
  key: string;
  name_en: string;
  name_ar: string;
  version: string;
  fields: DocumentTypeField[];
  rules_count: number;
  is_active: boolean;
}

export interface Integration {
  key: string;
  name: string;
  category: string;
  status: IntegrationStatus;
  detail: string;
  docs_url?: string;
}

export interface ModeInfo {
  mode: AppMode;
  version: string;
  features: Record<string, boolean>;
}

/* ---------------------------------- audit --------------------------------- */

export interface AuditEntry {
  id: string;
  case_id: string | null;
  case_reference: string | null;
  actor: string;
  actor_type: ActorType;
  action: string;
  label: string;
  detail: Record<string, unknown> | null;
  prompt_version: string | null;
  model_version: string | null;
  ip_address: string | null;
  created_at: string;
}

/* --------------------------------- system --------------------------------- */

export interface StackItem {
  name: string;
  version: string;
  why: string;
  alternative: string;
}

export interface SystemInfo {
  mode: AppMode;
  version: string;
  build_sha: string;
  started_at: string;
  stack: { layer: string; items: StackItem[] }[];
  services: {
    name: string;
    status: "healthy" | "degraded" | "down" | "disabled";
    detail: string;
  }[];
  diagrams: { key: string; title: string; mermaid: string }[];
}

export interface SystemGraph {
  mermaid: string;
}

/* ---------------------------- pipeline / events --------------------------- */

export interface CaseProgressEvent {
  node: string;
  status: string;
  message: string;
  percent: number;
  timeline_event?: TimelineEvent;
}

export interface StartCaseResponse {
  thread_id: string;
  status: CaseStatus;
}

/* ------------------------------- assurance -------------------------------- */

/** The evidence behind one case, read from the agent's own checkpoint. */
export interface CaseAssurance {
  available: boolean; // false for a seeded case that never ran through the graph
  note: string;
  thread_id: string;
  guardrails: GuardrailReport[];
  worker_results: WorkerResult[];
  critic_notes: CriticNote[];
  investigation: InvestigationStep[];
  tool_calls: ToolCall[];
  plan: PlanItem[];
  rule_packs: Record<string, string>; // doc type -> "trade_license@1.2.0"
  prompt_versions: Record<string, string>;
  calibration: CalibrationCurve;
  review_reasons: { code: string; label: string }[];
}

export interface GuardrailReport {
  document_id: string;
  filename: string;
  blocked: boolean;
  sanitised: boolean;
  pii_counts: Record<string, number>;
  injection: {
    attacked: boolean;
    risk: number;
    engine: string;
    signals: { kind: string; pattern: string; excerpt: string }[];
  };
  safety: {
    flagged: boolean;
    severities: Record<string, number>;
    matches: string[];
    engine: string;
  };
}

export interface WorkerResult {
  document_id: string;
  filename: string;
  doc_type: string;
  field_count: number;
  attempts: number;
  validated: boolean;
  duration_ms: number;
  model_version: string;
  prompt_version: string;
  repairs: {
    field: string;
    pass: string;
    strategy: string;
    error: string;
    explanation: string;
    before: string;
    after: string;
  }[];
  examples: { id: string; doc_type: string; note: string; similarity: number }[];
}

export interface CriticNote {
  field: string;
  agreed: boolean;
  reason: string;
  via: string; // "mcp:document_store" or "local"
  suggested_value: string | null;
}

export interface InvestigationStep {
  index: number;
  thought: string;
  action: string;
  action_input: Record<string, unknown>;
  observation: string;
  ok: boolean;
  duration_ms: number;
}

export interface ToolCall {
  server: string;
  tool: string;
  arguments: Record<string, unknown>;
  ok: boolean;
  duration_ms: number;
  result: Record<string, unknown> | null;
  error: string | null;
}

export interface PlanItem {
  document_id: string;
  filename: string;
  doc_type: string;
  classification_confidence: number;
  evidence: string[];
  field_count: number;
  worker: string;
  dispatched: boolean;
  skipped_because: string;
  prompt_version: string;
}

/** How the agent assures its answers, read from the code that runs. */
export interface AssuranceInfo {
  guardrails: { key: string; name: string; purpose: string; implementation: string; azure: string }[];
  confidence_signals: { key: string; label: string; weight: number }[];
  tool_servers: ToolServer[];
  rule_packs: RulePack[];
  registered_checks: string[];
  graph_steps: { key: string; label: string }[];
  policy_documents: { name: string; sections: number }[];
  embedder: string;
  calibration: CalibrationCurve;
}

export interface ToolServer {
  key: string;
  name: string;
  url_configured: boolean;
  can_write: boolean;
  tools: string[];
  used_by_nodes: string[];
}

export interface RulePack {
  id: string;
  version: string;
  title: string;
  description: string;
  applies_to: string[];
  source: string;
  rules: RuleOut[];
}

export interface RuleOut {
  id: string;
  severity: Severity;
  message: string;
  policy: string | null;
  explain: string;
  expr: string | null;
  check: string | null;
}
