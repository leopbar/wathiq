import type {
  CaseStatus,
  CaseType,
  DocTypeKey,
  Priority,
  ReviewDecision,
  RiskLevel,
  Role,
  Severity,
  SlaState,
} from "./types";

export const CASE_STATUSES: CaseStatus[] = [
  "intake",
  "processing",
  "needs_review",
  "in_review",
  "approved",
  "posting",
  "completed",
  "rejected",
  "failed",
];

export const CASE_STATUS_LABEL: Record<CaseStatus, string> = {
  intake: "Intake",
  processing: "Processing",
  needs_review: "Needs review",
  in_review: "In review",
  approved: "Approved",
  posting: "Posting",
  completed: "Completed",
  rejected: "Rejected",
  failed: "Failed",
};

export const CASE_TYPES: CaseType[] = ["kyc_refresh", "salary_certificate"];

export const CASE_TYPE_LABEL: Record<CaseType, string> = {
  kyc_refresh: "Corporate KYC refresh",
  salary_certificate: "Salary certificate",
};

export const PRIORITIES: Priority[] = ["normal", "high", "urgent"];

export const PRIORITY_LABEL: Record<Priority, string> = {
  normal: "Normal",
  high: "High",
  urgent: "Urgent",
};

export const RISK_LABEL: Record<RiskLevel, string> = {
  low: "Low risk",
  medium: "Medium risk",
  high: "High risk",
};

export const SLA_STATES: SlaState[] = ["on_track", "at_risk", "breached", "none"];

export const SLA_LABEL: Record<SlaState, string> = {
  on_track: "On track",
  at_risk: "At risk",
  breached: "Breached",
  none: "No SLA",
};

export const SEVERITY_LABEL: Record<Severity, string> = {
  info: "Info",
  warning: "Warning",
  critical: "Critical",
};

export const DOC_TYPE_LABEL: Record<DocTypeKey, string> = {
  trade_license: "Trade licence",
  emirates_id: "Emirates ID",
  passport: "Passport",
  moa: "Memorandum of association",
  salary_certificate: "Salary certificate",
  unknown: "Unclassified",
};

export const ROLE_LABEL: Record<Role, string> = {
  ops_officer: "Operations Officer",
  reviewer: "Reviewer",
  supervisor: "Supervisor",
  admin: "Administrator",
  auditor: "Auditor",
};

export const DECISION_LABEL: Record<ReviewDecision, string> = {
  approve: "Approve",
  correct: "Correct",
  reject: "Reject",
  escalate: "Escalate",
};

/**
 * The steps of the real graph, in order. Mirrors `STEPS` in `app/services/progress.py` on the
 * backend, which is what turns event-log rows into the frames this list renders.
 *
 * Guardrails are not here yet: they are built in M3, and a step that never lights up reads as
 * a broken pipeline rather than an honest "not built".
 */
export const PIPELINE_NODES = [
  { key: "intake", label: "Intake", description: "Documents received and stored" },
  { key: "ocr", label: "Read text", description: "Text pulled out of each document" },
  { key: "classify", label: "Classify", description: "Decide what each document is" },
  { key: "extract", label: "Extract", description: "Pull the schema's fields out" },
  { key: "validate", label: "Validate", description: "Cross-field rules and confidence" },
  { key: "review_gate", label: "Review gate", description: "Human-in-the-loop interrupt" },
  { key: "finalize", label: "Finalize", description: "Close the case and audit" },
] as const;

export const ACCEPTED_MIME = [
  "application/pdf",
  "image/png",
  "image/jpeg",
  "image/tiff",
] as const;

export const ACCEPTED_EXTENSIONS = ".pdf,.png,.jpg,.jpeg,.tif,.tiff";
export const MAX_FILE_BYTES = 20 * 1024 * 1024;
export const MAX_FILES = 12;

export const PAGE_SIZE = 20;

export const LANG_KEY = "wathiq.lang";
export const THEME_KEY = "wathiq.theme";
export const SIDEBAR_KEY = "wathiq.sidebar";
