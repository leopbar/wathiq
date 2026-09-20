import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  Clock,
  GitBranch,
  Lock,
  Timer,
  XCircle,
} from "lucide-react";
import { apiFetch } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import { qk } from "@/lib/query";
import type {
  AuditIntegrity,
  EngineHealth,
  ProcessHealth,
  ProcessStepDefinition,
  SlaSweepResult,
} from "@/lib/types";
import { useAuth } from "@/auth/useAuth";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ListSkeleton } from "@/components/Skeletons";
import { ErrorState } from "@/components/ErrorState";
import { MermaidDiagram } from "@/components/MermaidDiagram";
import { Tooltip } from "@/components/ui/tooltip";

/**
 * The process layer, as the running system reports it.
 *
 * Two engines can run the business process: Orkes Conductor, or an in-process fallback for a
 * machine that cannot spare Conductor's memory. This page says which one is actually in use and
 * what each one can do — including, plainly, when Conductor was wanted and could not be reached.
 * A demo running on the fallback must never look like one running on Conductor.
 */

const KIND_LABEL: Record<string, string> = {
  simple: "worker task",
  human: "human task",
  wait: "timer",
  switch: "decision",
  join: "join",
  fork: "fork",
};

function EngineCard({ health, active }: { health: EngineHealth; active: boolean }) {
  const isConductor = health.engine === "conductor";
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-small font-semibold text-ink">
            {isConductor ? "Orkes Conductor" : "In-process engine (fallback)"}
          </p>
          {health.url ? (
            <code className="text-caption text-ink-2" dir="ltr">
              {health.url}
            </code>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          {active ? <Badge tone="primary">in use</Badge> : <Badge tone="outline">standby</Badge>}
          {health.reachable ? (
            <Badge tone="success">
              <CheckCircle2 className="h-3 w-3" aria-hidden />
              reachable
            </Badge>
          ) : (
            <Badge tone="danger">
              <XCircle className="h-3 w-3" aria-hidden />
              not reachable
            </Badge>
          )}
        </div>
      </div>
      <p className="mt-2 text-caption text-ink-2">{health.detail}</p>
      {isConductor ? (
        <p className="mt-2 text-caption text-ink-2">
          {health.workflow_registered
            ? "The workflow definition in this repository is registered on the server."
            : "The workflow is not registered yet. A worker registers it when it starts."}
        </p>
      ) : null}
    </Card>
  );
}

function StepRow({ step }: { step: ProcessStepDefinition }) {
  return (
    <li className="flex items-start gap-3 border-b border-border px-4 py-3 last:border-b-0">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-small font-medium text-ink">{step.label}</span>
          <Badge tone="outline">{KIND_LABEL[step.kind] ?? step.kind}</Badge>
          {step.queue ? (
            <code className="text-caption text-ink-2" dir="ltr">
              {step.queue}
            </code>
          ) : null}
          {step.writes_externally ? (
            <Tooltip content="The only step that changes something outside Wathiq. It refuses without an approval and carries an idempotency key.">
              <span className="inline-flex">
                <Badge tone="warning">
                  <Building2 className="h-3 w-3" aria-hidden />
                  writes externally
                </Badge>
              </span>
            </Tooltip>
          ) : null}
          {step.only_on_route ? (
            <Badge tone="neutral">only when a human is asked</Badge>
          ) : null}
        </div>
        <p className="mt-1 text-caption text-ink-2">{step.description}</p>
      </div>
    </li>
  );
}

function AuditIntegrityCard() {
  const query = useQuery({
    queryKey: qk.auditIntegrity,
    queryFn: () => apiFetch<AuditIntegrity>("/process/audit-integrity"),
  });

  if (query.isPending) return <ListSkeleton rows={2} />;
  if (query.isError) {
    return (
      <Card>
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      </Card>
    );
  }

  const report = query.data;
  return (
    <Card className="p-4" aria-label="Audit trail integrity" role="region">
      <div className="flex flex-wrap items-center gap-2">
        <Lock className="h-4 w-4 text-ink-2" aria-hidden />
        <span className="text-small font-semibold text-ink">Audit trail</span>
        {report.append_only_enforced ? (
          <Badge tone="success">append-only, enforced by the database</Badge>
        ) : (
          <Badge tone="danger">
            <AlertTriangle className="h-3 w-3" aria-hidden />
            not enforced
          </Badge>
        )}
        <Badge tone="neutral">{formatNumber(report.rows)} entries</Badge>
      </div>
      <p className="mt-2 text-caption text-ink-2">{report.detail}</p>
      {/* The limits of the check are shown, not buried: it proves the application cannot
          rewrite the log, and it does not claim to be cryptographic proof. */}
      <p className="mt-2 text-caption text-ink-2">
        <span className="font-medium text-ink">What this does not prove: </span>
        {report.limits}
      </p>
    </Card>
  );
}

export function ProcessTab() {
  const { role } = useAuth();
  const canSweep = role === "supervisor" || role === "admin";
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: qk.processHealth,
    queryFn: () => apiFetch<ProcessHealth>("/process/health"),
  });

  const sweep = useMutation({
    mutationFn: () =>
      apiFetch<SlaSweepResult>("/process/sla/sweep", { method: "POST" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["review"] });
    },
  });

  if (query.isPending) return <ListSkeleton rows={4} />;
  if (query.isError) {
    return (
      <Card>
        <ErrorState
          error={query.error}
          onRetry={() => void query.refetch()}
          title="The process layer could not be read"
        />
      </Card>
    );
  }

  const health = query.data;

  return (
    <section aria-label="Process layer" className="space-y-4">
      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-2">
          <GitBranch className="h-4 w-4 text-ink-2" aria-hidden />
          <span className="text-small font-semibold text-ink">
            {health.process.workflow} v{health.process.version}
          </span>
          <Badge tone="outline">configured: {health.configured}</Badge>
          <Badge tone={health.active === "conductor" ? "primary" : "info"}>
            running on: {health.active === "conductor" ? "Conductor" : "the in-process engine"}
          </Badge>
          {health.fell_back ? (
            <Badge tone="warning">
              <AlertTriangle className="h-3 w-3" aria-hidden />
              Conductor unreachable — using the fallback
            </Badge>
          ) : null}
        </div>
        <p className="mt-2 text-caption text-ink-2">
          Conductor runs the business process and can wait days for a person. LangGraph runs the AI
          reasoning inside one of its tasks. The Conductor workflow id is the LangGraph thread id,
          so a single identifier ties the process, the reasoning and the audit trail together.
        </p>
        <p className="mt-2 text-caption text-ink-2">
          Each case records which engine ran it, so a case processed by the fallback can never be
          mistaken for one that went through Conductor.
        </p>
      </Card>

      <div className="grid gap-3 lg:grid-cols-2">
        {health.engines.map((engine) => (
          <EngineCard
            key={engine.engine}
            health={engine}
            active={engine.engine === health.active}
          />
        ))}
      </div>

      <Card>
        <CardHeader
          title="The workflow"
          description="Generated from the definition in the code, so it cannot draw a process we do not run."
        />
        <div className="p-4">
          <MermaidDiagram
            chart={health.process.mermaid}
            ariaLabel="The Conductor workflow Wathiq runs for a KYC refresh"
          />
        </div>
      </Card>

      <Card>
        <CardHeader
          title="Steps"
          description={`${health.process.steps.length} steps. Worker queues: ${health.process.worker_queues.join(", ")}`}
        />
        <ul>
          {health.process.steps.map((step) => (
            <StepRow key={step.ref} step={step} />
          ))}
        </ul>
      </Card>

      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-2">
          <Timer className="h-4 w-4 text-ink-2" aria-hidden />
          <span className="text-small font-semibold text-ink">Review SLA</span>
          <Badge tone="neutral">
            <Clock className="h-3 w-3" aria-hidden />
            {health.process.sla_hours} hours
          </Badge>
        </div>
        <p className="mt-2 text-caption text-ink-2">
          The timer runs beside the human review, not after it. If it fires first, the review moves
          to the supervisor queue and the case priority is raised — the case is never decided or
          cancelled on a person's behalf. A review someone is already working on stays with them.
        </p>
        {canSweep ? (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              onClick={() => sweep.mutate()}
              disabled={sweep.isPending}
            >
              {sweep.isPending ? "Checking…" : "Run the SLA check now"}
            </Button>
            <span className="text-caption text-ink-2">
              The same sweep the timer runs. It can only escalate a review that is already overdue.
            </span>
            {sweep.data ? (
              <Badge tone={sweep.data.escalated > 0 ? "warning" : "success"}>
                {sweep.data.note}
              </Badge>
            ) : null}
            {sweep.isError ? <Badge tone="danger">The check could not be run</Badge> : null}
          </div>
        ) : (
          <p className="mt-3 text-caption text-ink-2">
            Only a supervisor or an admin can run the SLA check by hand.
          </p>
        )}
      </Card>

      <AuditIntegrityCard />
    </section>
  );
}
