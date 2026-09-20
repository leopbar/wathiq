import type { CaseStatus, Priority, RiskLevel, Severity } from "@/lib/types";
import { CASE_STATUS_LABEL, PRIORITY_LABEL, RISK_LABEL, SEVERITY_LABEL } from "@/lib/constants";
import { Badge } from "./ui/badge";
import type { BadgeProps } from "./ui/badge";

type Tone = NonNullable<BadgeProps["tone"]>;

const STATUS_TONE: Record<CaseStatus, Tone> = {
  intake: "neutral",
  processing: "info",
  needs_review: "warning",
  in_review: "warning",
  approved: "success",
  posting: "info",
  completed: "success",
  rejected: "danger",
  failed: "danger",
};

const DOT: Record<Tone, string> = {
  neutral: "bg-ink-2",
  primary: "bg-primary",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  info: "bg-info",
  outline: "bg-ink-2",
};

export function StatusPill({ status }: { status: CaseStatus }) {
  const tone = STATUS_TONE[status];
  return (
    <Badge tone={tone}>
      <span className={`h-1.5 w-1.5 rounded-full ${DOT[tone]}`} aria-hidden />
      {CASE_STATUS_LABEL[status]}
    </Badge>
  );
}

const SEVERITY_TONE: Record<Severity, Tone> = {
  info: "info",
  warning: "warning",
  critical: "danger",
};

export function SeverityPill({ severity }: { severity: Severity }) {
  const tone = SEVERITY_TONE[severity];
  return (
    <Badge tone={tone}>
      <span className={`h-1.5 w-1.5 rounded-full ${DOT[tone]}`} aria-hidden />
      {SEVERITY_LABEL[severity]}
    </Badge>
  );
}

const PRIORITY_TONE: Record<Priority, Tone> = {
  normal: "outline",
  high: "warning",
  urgent: "danger",
};

export function PriorityPill({ priority }: { priority: Priority }) {
  if (priority === "normal") {
    return <span className="text-small text-ink-2">{PRIORITY_LABEL.normal}</span>;
  }
  return <Badge tone={PRIORITY_TONE[priority]}>{PRIORITY_LABEL[priority]}</Badge>;
}

const RISK_TONE: Record<RiskLevel, Tone> = {
  low: "outline",
  medium: "warning",
  high: "danger",
};

export function RiskPill({ risk }: { risk: RiskLevel }) {
  return <Badge tone={RISK_TONE[risk]}>{RISK_LABEL[risk]}</Badge>;
}
