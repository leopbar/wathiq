import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
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

const KNOWN_KINDS = ["simple", "human", "wait", "switch", "join", "fork"];

function EngineCard({ health, active }: { health: EngineHealth; active: boolean }) {
  const { t } = useTranslation();
  const isConductor = health.engine === "conductor";
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-small font-semibold text-ink">
            {isConductor ? "Orkes Conductor" : t("settings.process.fallbackEngine")}
          </p>
          {health.url ? (
            <code className="text-caption text-ink-2" dir="ltr">
              {health.url}
            </code>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          {active ? (
            <Badge tone="primary">{t("settings.process.inUse")}</Badge>
          ) : (
            <Badge tone="outline">{t("settings.process.standby")}</Badge>
          )}
          {health.reachable ? (
            <Badge tone="success">
              <CheckCircle2 className="h-3 w-3" aria-hidden />
              {t("settings.process.reachable")}
            </Badge>
          ) : (
            <Badge tone="danger">
              <XCircle className="h-3 w-3" aria-hidden />
              {t("settings.process.notReachable")}
            </Badge>
          )}
        </div>
      </div>
      <p className="mt-2 text-caption text-ink-2">{health.detail}</p>
      {isConductor ? (
        <p className="mt-2 text-caption text-ink-2">
          {health.workflow_registered
            ? t("settings.process.workflowRegistered")
            : t("settings.process.workflowNotRegistered")}
        </p>
      ) : null}
    </Card>
  );
}

function StepRow({ step }: { step: ProcessStepDefinition }) {
  const { t } = useTranslation();
  return (
    <li className="flex items-start gap-3 border-b border-border px-4 py-3 last:border-b-0">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-small font-medium text-ink">{step.label}</span>
          <Badge tone="outline">
            {KNOWN_KINDS.includes(step.kind) ? t(`settings.process.kind.${step.kind}`) : step.kind}
          </Badge>
          {step.queue ? (
            <code className="text-caption text-ink-2" dir="ltr">
              {step.queue}
            </code>
          ) : null}
          {step.writes_externally ? (
            <Tooltip content={t("settings.process.writesExternallyHint")}>
              <span className="inline-flex">
                <Badge tone="warning">
                  <Building2 className="h-3 w-3" aria-hidden />
                  {t("settings.process.writesExternally")}
                </Badge>
              </span>
            </Tooltip>
          ) : null}
          {step.only_on_route ? (
            <Badge tone="neutral">{t("settings.process.onlyOnRoute")}</Badge>
          ) : null}
        </div>
        <p className="mt-1 text-caption text-ink-2">{step.description}</p>
      </div>
    </li>
  );
}

function AuditIntegrityCard() {
  const { t } = useTranslation();
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
    <Card className="p-4" aria-label={t("settings.process.auditIntegrityLabel")} role="region">
      <div className="flex flex-wrap items-center gap-2">
        <Lock className="h-4 w-4 text-ink-2" aria-hidden />
        <span className="text-small font-semibold text-ink">
          {t("settings.process.auditTrail")}
        </span>
        {report.append_only_enforced ? (
          <Badge tone="success">{t("settings.process.appendOnly")}</Badge>
        ) : (
          <Badge tone="danger">
            <AlertTriangle className="h-3 w-3" aria-hidden />
            {t("settings.process.notEnforced")}
          </Badge>
        )}
        <Badge tone="neutral">
          {t("settings.process.entries", {
            count: report.rows,
            formatted: formatNumber(report.rows),
          })}
        </Badge>
      </div>
      <p className="mt-2 text-caption text-ink-2">{report.detail}</p>
      {/* The limits of the check are shown, not buried: it proves the application cannot
          rewrite the log, and it does not claim to be cryptographic proof. */}
      <p className="mt-2 text-caption text-ink-2">
        <span className="font-medium text-ink">{t("settings.process.doesNotProve")} </span>
        {report.limits}
      </p>
    </Card>
  );
}

export function ProcessTab() {
  const { t } = useTranslation();
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
          title={t("settings.process.loadError")}
        />
      </Card>
    );
  }

  const health = query.data;

  return (
    <section aria-label={t("settings.process.regionLabel")} className="space-y-4">
      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-2">
          <GitBranch className="h-4 w-4 text-ink-2" aria-hidden />
          <span className="text-small font-semibold text-ink" dir="ltr">
            {health.process.workflow} v{health.process.version}
          </span>
          <Badge tone="outline">
            {t("settings.process.configured", { engine: health.configured })}
          </Badge>
          <Badge tone={health.active === "conductor" ? "primary" : "info"}>
            {t("settings.process.runningOn", {
              engine:
                health.active === "conductor"
                  ? "Conductor"
                  : t("settings.process.inProcessEngine"),
            })}
          </Badge>
          {health.fell_back ? (
            <Badge tone="warning">
              <AlertTriangle className="h-3 w-3" aria-hidden />
              {t("settings.process.fellBack")}
            </Badge>
          ) : null}
        </div>
        <p className="mt-2 text-caption text-ink-2">{t("settings.process.twoLayers")}</p>
        <p className="mt-2 text-caption text-ink-2">{t("settings.process.engineRecorded")}</p>
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
          title={t("settings.process.workflowTitle")}
          description={t("settings.process.workflowDescription")}
        />
        <div className="p-4" dir="ltr">
          <MermaidDiagram
            chart={health.process.mermaid}
            ariaLabel={t("settings.process.workflowAria")}
          />
        </div>
      </Card>

      <Card>
        <CardHeader
          title={t("settings.process.stepsTitle")}
          description={t("settings.process.stepsDescription", {
            count: health.process.steps.length,
            queues: health.process.worker_queues.join(", "),
          })}
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
          <span className="text-small font-semibold text-ink">
            {t("settings.process.reviewSla")}
          </span>
          <Badge tone="neutral">
            <Clock className="h-3 w-3" aria-hidden />
            {t("settings.process.hours", { count: health.process.sla_hours })}
          </Badge>
        </div>
        <p className="mt-2 text-caption text-ink-2">{t("settings.process.slaBody")}</p>
        {canSweep ? (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              onClick={() => sweep.mutate()}
              disabled={sweep.isPending}
            >
              {sweep.isPending ? t("settings.process.checking") : t("settings.process.runSweep")}
            </Button>
            <span className="text-caption text-ink-2">{t("settings.process.sweepNote")}</span>
            {sweep.data ? (
              <Badge tone={sweep.data.escalated > 0 ? "warning" : "success"}>
                {sweep.data.note}
              </Badge>
            ) : null}
            {sweep.isError ? (
              <Badge tone="danger">{t("settings.process.sweepError")}</Badge>
            ) : null}
          </div>
        ) : (
          <p className="mt-3 text-caption text-ink-2">{t("settings.process.sweepForbidden")}</p>
        )}
      </Card>

      <AuditIntegrityCard />
    </section>
  );
}
