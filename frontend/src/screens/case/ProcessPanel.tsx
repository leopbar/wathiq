import {
  AlertTriangle,
  Ban,
  Building2,
  CheckCircle2,
  Circle,
  GitBranch,
  Hourglass,
  Loader2,
  ShieldAlert,
  UserCheck,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import type { ProcessStatus, ProcessStep, ProcessStepStatus } from "@/lib/types";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { CopyButton } from "@/components/ui/code-block";

/**
 * Where this case is in the business process.
 *
 * Every row is read from the case's append-only event log, which is the same record the audit
 * trail shows. A step that says "completed" has an entry behind it; a step that says "pending"
 * has none. Nothing here is inferred from the case status, so the panel cannot flatter a run
 * that stopped half way.
 *
 * When Conductor ran the case, its own view of the workflow instance is shown underneath — two
 * independent records of the same run, side by side.
 */

const STEP_TONE: Record<ProcessStepStatus, { icon: typeof Circle; className: string }> = {
  completed: { icon: CheckCircle2, className: "text-success" },
  running: { icon: Loader2, className: "text-primary animate-spin" },
  waiting: { icon: Hourglass, className: "text-warning" },
  skipped: { icon: Ban, className: "text-ink-2" },
  failed: { icon: AlertTriangle, className: "text-danger" },
  pending: { icon: Circle, className: "text-ink-2/50" },
};

const KNOWN_KINDS = ["simple", "human", "wait", "switch", "join", "fork"];

function StepRow({ step }: { step: ProcessStep }) {
  const { t } = useTranslation();
  const tone = STEP_TONE[step.status];
  const Icon = tone.icon;
  return (
    <li className="flex items-start gap-3 px-4 py-3">
      <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", tone.className)} aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={cn(
              "text-small font-medium",
              step.status === "pending" ? "text-ink-2" : "text-ink",
            )}
          >
            {step.label}
          </span>
          <Badge tone="outline">
            {KNOWN_KINDS.includes(step.kind) ? t(`settings.process.kind.${step.kind}`) : step.kind}
          </Badge>
          {step.writes_externally ? (
            <Badge tone="warning">
              <Building2 className="h-3 w-3" aria-hidden />
              {t("caseDetail.process.writesCoreBanking")}
            </Badge>
          ) : null}
        </div>
        {step.detail ? <p className="mt-1 text-caption text-ink-2">{step.detail}</p> : null}
      </div>
      <div className="shrink-0 text-end">
        <div className="text-caption text-ink-2">{t(`caseDetail.process.stepStatus.${step.status}`)}</div>
        {step.at ? (
          <div className="text-caption text-ink-2 tabular">
            <bdi>{formatDateTime(step.at)}</bdi>
          </div>
        ) : null}
      </div>
    </li>
  );
}

function EngineBadge({ engine }: { engine: string }) {
  const { t } = useTranslation();
  if (engine === "conductor") {
    return (
      <Badge tone="primary">
        <GitBranch className="h-3 w-3" aria-hidden />
        Orkes Conductor
      </Badge>
    );
  }
  return (
    <Badge tone="info">
      <GitBranch className="h-3 w-3" aria-hidden />
      {t("caseDetail.process.inProcessEngine")}
    </Badge>
  );
}

function PostingCard({ posting }: { posting: NonNullable<ProcessStatus["posting"]> }) {
  const { t } = useTranslation();
  const posted = posting.status === "posted";
  return (
    <section
      aria-label={t("caseDetail.process.postingTitle")}
      className="rounded-lg border border-border bg-surface-2/50 p-3"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-small font-medium text-ink">
          {t("caseDetail.process.postingTitle")}
        </span>
        <Badge tone={posted ? "success" : posting.status === "failed" ? "danger" : "neutral"}>
          {t(`caseDetail.process.postingStatus.${posting.status}`, { defaultValue: posting.status })}
        </Badge>
        {/* Said on the row itself, not only in a legend: nothing here reached a real bank. */}
        <Badge tone="warning">
          <ShieldAlert className="h-3 w-3" aria-hidden />
          {t("caseDetail.process.simulated")}
        </Badge>
        {posting.duplicate ? <Badge tone="info">{t("caseDetail.process.duplicate")}</Badge> : null}
      </div>
      <p className="mt-2 text-caption text-ink-2">{posting.note}</p>
      <dl className="mt-3 grid gap-2 sm:grid-cols-2">
        {posting.reference ? (
          <div>
            <dt className="label-caption text-ink-2">{t("caseDetail.process.reference")}</dt>
            <dd className="mt-0.5 flex items-center gap-1 text-caption text-ink tabular" dir="ltr">
              <span className="truncate">{posting.reference}</span>
              <CopyButton value={posting.reference} />
            </dd>
          </div>
        ) : null}
        {posting.customer_id ? (
          <div>
            <dt className="label-caption text-ink-2">{t("caseDetail.process.customerFile")}</dt>
            <dd className="mt-0.5 text-caption text-ink tabular" dir="ltr">
              {posting.customer_id}
            </dd>
          </div>
        ) : null}
        {posting.approved_by ? (
          <div>
            <dt className="label-caption text-ink-2">{t("caseDetail.process.approvedBy")}</dt>
            <dd className="mt-0.5 flex flex-wrap items-center gap-1.5 text-caption text-ink">
              {posting.approved_by}
              <Badge tone={posting.approval_kind === "human" ? "success" : "info"}>
                {posting.approval_kind === "human" ? (
                  <>
                    <UserCheck className="h-3 w-3" aria-hidden />
                    {t("caseDetail.process.aPerson")}
                  </>
                ) : (
                  t("caseDetail.process.aPolicy")
                )}
              </Badge>
            </dd>
          </div>
        ) : null}
        <div className="sm:col-span-2">
          <dt className="label-caption text-ink-2">{t("caseDetail.process.idempotencyKey")}</dt>
          <dd className="mt-0.5 flex items-center gap-1 text-caption text-ink-2 tabular" dir="ltr">
            <span className="truncate">{posting.idempotency_key}</span>
            {posting.idempotency_key ? <CopyButton value={posting.idempotency_key} /> : null}
          </dd>
        </div>
      </dl>
    </section>
  );
}

export function ProcessPanel({ status }: { status: ProcessStatus }) {
  const { t } = useTranslation();
  return (
    // A named landmark, so a screen reader can jump straight here — and so a test can anchor
    // to this panel instead of to words that also appear elsewhere on a busy case screen.
    <section aria-label={t("caseDetail.process.regionLabel")} className="divide-y divide-border">
      <section className="p-4">
        <div className="flex flex-wrap items-center gap-2">
          <EngineBadge engine={status.engine} />
          <Badge tone="outline">
            <bdi>
              {status.workflow_name} v{status.workflow_version}
            </bdi>
          </Badge>
          {status.route ? (
            <Badge tone="neutral">
              {status.route === "review"
                ? t("caseDetail.process.humanAsked")
                : t("caseDetail.process.straightThrough")}
            </Badge>
          ) : null}
          {status.escalated ? (
            <Badge tone="warning">
              <AlertTriangle className="h-3 w-3" aria-hidden />
              {t("caseDetail.process.slaEscalated")}
            </Badge>
          ) : null}
          {status.finished ? <Badge tone="success">{t("caseDetail.process.finished")}</Badge> : null}
        </div>
        <dl className="mt-3">
          <dt className="label-caption text-ink-2">
            {t("caseDetail.process.workflowId")}
          </dt>
          <dd className="mt-0.5 flex items-center gap-1 text-caption text-ink tabular" dir="ltr">
            <span className="truncate">{status.workflow_id}</span>
            <CopyButton value={status.workflow_id} />
          </dd>
        </dl>
        {status.note ? <p className="mt-2 text-caption text-ink-2">{status.note}</p> : null}
        {!status.started ? (
          <p className="mt-2 text-caption text-ink-2">
            {t("caseDetail.process.notStarted")}
          </p>
        ) : null}
      </section>

      <ul className="divide-y divide-border">
        {status.steps.map((step) => (
          <StepRow key={step.ref} step={step} />
        ))}
      </ul>

      {status.posting ? (
        <section className="p-4">
          <PostingCard posting={status.posting} />
        </section>
      ) : null}

      {status.live ? (
        <section className="p-4">
          <h3 className="text-small font-medium text-ink">{t("caseDetail.process.conductorSays")}</h3>
          <p className="mt-1 text-caption text-ink-2">
            {t("caseDetail.process.conductorSaysBody")}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Badge tone={status.live.status === "COMPLETED" ? "success" : "info"}>
              {status.live.status}
            </Badge>
            <span className="text-caption text-ink-2 tabular" dir="ltr">
              {status.live.workflow_id}
            </span>
          </div>
          <ul className="mt-3 space-y-1">
            {status.live.tasks.map((task) => (
              <li
                key={`${task.ref}-${task.type}`}
                className="flex flex-wrap items-center gap-2 text-caption"
              >
                <span className="text-ink tabular" dir="ltr">
                  {task.ref}
                </span>
                <span className="text-ink-2" dir="ltr">
                  {task.type}
                </span>
                <Badge tone={task.status === "COMPLETED" ? "success" : "neutral"}>
                  {task.status}
                </Badge>
                {task.retried > 0 ? <Badge tone="warning">{t("caseDetail.process.retried", { count: task.retried })}</Badge> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </section>
  );
}
