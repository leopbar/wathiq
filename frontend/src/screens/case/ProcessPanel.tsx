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

const STEP_TONE: Record<ProcessStepStatus, { icon: typeof Circle; className: string; label: string }> =
  {
    completed: { icon: CheckCircle2, className: "text-success", label: "done" },
    running: { icon: Loader2, className: "text-primary animate-spin", label: "running" },
    waiting: { icon: Hourglass, className: "text-warning", label: "waiting for a person" },
    skipped: { icon: Ban, className: "text-ink-2", label: "not needed" },
    failed: { icon: AlertTriangle, className: "text-danger", label: "failed" },
    pending: { icon: Circle, className: "text-ink-2/50", label: "not yet" },
  };

const KIND_LABEL: Record<string, string> = {
  simple: "worker task",
  human: "human task",
  wait: "timer",
  switch: "decision",
  join: "join",
  fork: "fork",
};

function StepRow({ step }: { step: ProcessStep }) {
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
          <Badge tone="outline">{KIND_LABEL[step.kind] ?? step.kind}</Badge>
          {step.writes_externally ? (
            <Badge tone="warning">
              <Building2 className="h-3 w-3" aria-hidden />
              writes to core banking
            </Badge>
          ) : null}
        </div>
        {step.detail ? <p className="mt-1 text-caption text-ink-2">{step.detail}</p> : null}
      </div>
      <div className="shrink-0 text-end">
        <div className="text-caption text-ink-2">{tone.label}</div>
        {step.at ? (
          <div className="text-caption text-ink-2 tabular">{formatDateTime(step.at)}</div>
        ) : null}
      </div>
    </li>
  );
}

function EngineBadge({ engine }: { engine: string }) {
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
      In-process engine
    </Badge>
  );
}

function PostingCard({ posting }: { posting: NonNullable<ProcessStatus["posting"]> }) {
  const posted = posting.status === "posted";
  return (
    <section
      aria-label="Core banking posting"
      className="rounded-lg border border-border bg-surface-2/50 p-3"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-small font-medium text-ink">Core banking posting</span>
        <Badge tone={posted ? "success" : posting.status === "failed" ? "danger" : "neutral"}>
          {posting.status}
        </Badge>
        {/* Said on the row itself, not only in a legend: nothing here reached a real bank. */}
        <Badge tone="warning">
          <ShieldAlert className="h-3 w-3" aria-hidden />
          simulated
        </Badge>
        {posting.duplicate ? <Badge tone="info">already posted — key recognised</Badge> : null}
      </div>
      <p className="mt-2 text-caption text-ink-2">{posting.note}</p>
      <dl className="mt-3 grid gap-2 sm:grid-cols-2">
        {posting.reference ? (
          <div>
            <dt className="label-caption text-ink-2">Reference</dt>
            <dd className="mt-0.5 flex items-center gap-1 text-caption text-ink tabular" dir="ltr">
              <span className="truncate">{posting.reference}</span>
              <CopyButton value={posting.reference} />
            </dd>
          </div>
        ) : null}
        {posting.customer_id ? (
          <div>
            <dt className="label-caption text-ink-2">Customer file</dt>
            <dd className="mt-0.5 text-caption text-ink tabular" dir="ltr">
              {posting.customer_id}
            </dd>
          </div>
        ) : null}
        {posting.approved_by ? (
          <div>
            <dt className="label-caption text-ink-2">Approved by</dt>
            <dd className="mt-0.5 flex flex-wrap items-center gap-1.5 text-caption text-ink">
              {posting.approved_by}
              <Badge tone={posting.approval_kind === "human" ? "success" : "info"}>
                {posting.approval_kind === "human" ? (
                  <>
                    <UserCheck className="h-3 w-3" aria-hidden />a person
                  </>
                ) : (
                  "a policy, not a person"
                )}
              </Badge>
            </dd>
          </div>
        ) : null}
        <div className="sm:col-span-2">
          <dt className="label-caption text-ink-2">Idempotency key</dt>
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
  return (
    // A named landmark, so a screen reader can jump straight here — and so a test can anchor
    // to this panel instead of to words that also appear elsewhere on a busy case screen.
    <section aria-label="Business process" className="divide-y divide-border">
      <section className="p-4">
        <div className="flex flex-wrap items-center gap-2">
          <EngineBadge engine={status.engine} />
          <Badge tone="outline">
            {status.workflow_name} v{status.workflow_version}
          </Badge>
          {status.route ? (
            <Badge tone="neutral">
              {status.route === "review" ? "a human was asked" : "straight through"}
            </Badge>
          ) : null}
          {status.escalated ? (
            <Badge tone="warning">
              <AlertTriangle className="h-3 w-3" aria-hidden />
              SLA escalated
            </Badge>
          ) : null}
          {status.finished ? <Badge tone="success">process finished</Badge> : null}
        </div>
        <dl className="mt-3">
          <dt className="label-caption text-ink-2">
            Workflow id — also the LangGraph thread id
          </dt>
          <dd className="mt-0.5 flex items-center gap-1 text-caption text-ink tabular" dir="ltr">
            <span className="truncate">{status.workflow_id}</span>
            <CopyButton value={status.workflow_id} />
          </dd>
        </dl>
        {status.note ? <p className="mt-2 text-caption text-ink-2">{status.note}</p> : null}
        {!status.started ? (
          <p className="mt-2 text-caption text-ink-2">
            This case has no recorded process start. Seeded demo cases are written straight to the
            database and never run through the workflow.
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
          <h3 className="text-small font-medium text-ink">What Conductor says</h3>
          <p className="mt-1 text-caption text-ink-2">
            Read from the orchestrator itself, next to Wathiq's own record above. They are kept by
            two different systems and should agree.
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
                <span className="text-ink-2">{task.type}</span>
                <Badge tone={task.status === "COMPLETED" ? "success" : "neutral"}>
                  {task.status}
                </Badge>
                {task.retried > 0 ? <Badge tone="warning">retried {task.retried}×</Badge> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </section>
  );
}
