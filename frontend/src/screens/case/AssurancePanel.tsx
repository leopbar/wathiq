import { useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Cpu,
  Search,
  Shield,
  Wrench,
  XCircle,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import type { CaseAssurance, CriticNote, GuardrailReport, WorkerResult } from "@/lib/types";
import { formatDuration, formatNumber, formatPercent } from "@/lib/format";
import { cn } from "@/lib/cn";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/EmptyState";
import { SimulatedBadge } from "@/components/SimulatedBadge";

/**
 * What the agent did to check its own work, for one case.
 *
 * Everything here is read from the agent's checkpoint, not from a summary written for the
 * screen. If the panel shows a tool call, that call happened; if it shows nothing, nothing
 * happened. That is the whole point of an assurance panel.
 */

function Section({
  icon: Icon,
  title,
  subtitle,
  badge,
  children,
  defaultOpen = false,
}: {
  icon: typeof Shield;
  title: string;
  subtitle: string;
  badge?: React.ReactNode;
  children: React.ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="border-b border-border last:border-b-0">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        className="flex w-full items-start gap-3 px-4 py-3 text-start hover:bg-surface-2/70"
      >
        <Icon className="mt-0.5 h-4 w-4 shrink-0 text-ink-2" aria-hidden />
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-small font-medium text-ink">{title}</span>
            {badge}
          </span>
          <span className="mt-0.5 block text-caption text-ink-2">{subtitle}</span>
        </span>
        <ChevronDown
          className={cn("mt-0.5 h-4 w-4 shrink-0 text-ink-2 transition-transform", open && "rotate-180")}
          aria-hidden
        />
      </button>
      {open ? <div className="px-4 pb-4">{children}</div> : null}
    </section>
  );
}

function Verdict({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  const Icon = ok ? CheckCircle2 : AlertTriangle;
  return (
    <p className={cn("flex items-start gap-1.5 text-caption", ok ? "text-ink-2" : "text-warning")}>
      <Icon className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
      <span>{children}</span>
    </p>
  );
}

function GuardrailCard({ report }: { report: GuardrailReport }) {
  const { t } = useTranslation();
  const piiTypes = Object.entries(report.pii_counts);
  return (
    <div className="rounded-lg border border-border bg-surface-2/50 p-3">
      <p className="truncate text-small font-medium text-ink" dir="ltr">
        {report.filename}
      </p>
      <div className="mt-2 space-y-1.5">
        <Verdict ok={!report.injection.attacked}>
          {report.injection.attacked
            ? t("caseDetail.assurance.shieldAttacked", {
                count: report.injection.signals.length,
                risk: formatPercent(report.injection.risk),
              })
            : t("caseDetail.assurance.shieldClear")}
        </Verdict>
        {report.injection.attacked ? (
          <ul className="ms-5 space-y-1">
            {report.injection.signals.slice(0, 4).map((signal, index) => (
              <li key={`${signal.kind}-${index}`} className="text-caption text-ink-2">
                <Badge tone="danger">
                  <bdi>{signal.kind}</bdi>
                </Badge>{" "}
                <bdi className="break-words">{signal.excerpt}</bdi>
              </li>
            ))}
          </ul>
        ) : null}
        <Verdict ok={!report.safety.flagged}>
          {report.safety.flagged
            ? t("caseDetail.assurance.safetyFlagged", { matches: report.safety.matches.join(", ") })
            : t("caseDetail.assurance.safetyClear")}
        </Verdict>
        <Verdict ok>
          {piiTypes.length === 0
            ? t("caseDetail.assurance.piiNone")
            : t("caseDetail.assurance.piiReplaced", {
                items: piiTypes.map(([label, count]) => `${count}× ${label}`).join(", "),
              })}
        </Verdict>
        <Verdict ok>
          {report.sanitised
            ? t("caseDetail.assurance.sanitised")
            : t("caseDetail.assurance.sanitiserClear")}
        </Verdict>
      </div>
    </div>
  );
}

function WorkerCard({ worker }: { worker: WorkerResult }) {
  const { t } = useTranslation();
  return (
    <div className="rounded-lg border border-border bg-surface-2/50 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="truncate text-small font-medium text-ink" dir="ltr">
          {worker.filename}
        </p>
        <span className="flex items-center gap-1.5">
          <Badge tone="neutral">
            {t("caseDetail.assurance.fields", { count: worker.field_count })}
          </Badge>
          <Badge tone={worker.attempts > 1 ? "warning" : "success"}>
            {t("caseDetail.assurance.attempts", { count: worker.attempts })}
          </Badge>
          <Badge tone="outline">{formatDuration(worker.duration_ms)}</Badge>
        </span>
      </div>

      {worker.repairs.length === 0 ? (
        <p className="mt-2 text-caption text-ink-2">
          {t("caseDetail.assurance.noRepairs")}
        </p>
      ) : (
        <ul className="mt-2 space-y-1.5">
          {worker.repairs.map((repair, index) => (
            <li key={`${repair.field}-${index}`} className="text-caption text-ink-2">
              <code className="font-medium text-ink" dir="ltr">
                {repair.field}
              </code>{" "}
              <Badge tone="outline">{t("caseDetail.assurance.pass", { pass: repair.pass })}</Badge>{" "}
              <Badge tone={repair.strategy === "drop" ? "danger" : "info"}>{repair.strategy}</Badge>
              <span className="mt-0.5 block">
                {repair.error}. {repair.explanation}
                {repair.after ? ` → ${repair.after}` : ` → ${t("caseDetail.assurance.leftEmpty")}`}
              </span>
            </li>
          ))}
        </ul>
      )}

      {worker.examples.length > 0 ? (
        <p className="mt-2 border-t border-border pt-2 text-caption text-ink-2">
          {t("caseDetail.assurance.fewShot")}{" "}
          <bdi>{worker.examples.map((example) => example.id).join(", ")}</bdi>{" "}
          <span className="text-ink-2/80">
            {t("caseDetail.assurance.fewShotNote")}
          </span>
        </p>
      ) : null}
    </div>
  );
}

function CriticRow({ note }: { note: CriticNote }) {
  const { t } = useTranslation();
  return (
    <li className="flex items-start gap-2 py-1.5">
      {note.agreed ? (
        <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" aria-hidden />
      ) : (
        <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-danger" aria-hidden />
      )}
      <span className="min-w-0 flex-1">
        <code className="text-small text-ink" dir="ltr">
          {note.field}
        </code>
        <span className="mt-0.5 block text-caption text-ink-2">{note.reason}</span>
      </span>
      <Badge tone="outline">{note.via === "local" ? t("caseDetail.assurance.inProcess") : note.via}</Badge>
    </li>
  );
}

export function AssurancePanel({ assurance }: { assurance: CaseAssurance }) {
  const { t } = useTranslation();
  if (!assurance.available) {
    return (
      <EmptyState
        icon={Shield}
        title={t("caseDetail.assurance.noCheckpoint")}
        description={assurance.note}
      />
    );
  }

  const disagreements = assurance.critic_notes.filter((note) => !note.agreed);
  const blocked = assurance.guardrails.filter((report) => report.blocked);
  const failedCalls = assurance.tool_calls.filter((call) => !call.ok);
  const dispatched = assurance.plan.filter((item) => item.dispatched);

  return (
    <div className="divide-y divide-border">
      <Section
        icon={Shield}
        title={t("caseDetail.assurance.guardrails")}
        subtitle={t("caseDetail.assurance.guardrailsSubtitle")}
        badge={
          blocked.length > 0 ? (
            <Badge tone="danger">
              {t("caseDetail.assurance.flagged", { count: blocked.length })}
            </Badge>
          ) : (
            <Badge tone="success">{t("caseDetail.assurance.allClear")}</Badge>
          )
        }
        defaultOpen={blocked.length > 0}
      >
        <div className="space-y-2">
          {assurance.guardrails.map((report) => (
            <GuardrailCard key={report.document_id} report={report} />
          ))}
        </div>
      </Section>

      <Section
        icon={Cpu}
        title={t("caseDetail.assurance.workers")}
        subtitle={t("caseDetail.assurance.workersSubtitle")}
        badge={
          <Badge tone="neutral">
            {t("caseDetail.assurance.inParallel", { count: dispatched.length })}
          </Badge>
        }
      >
        <ul className="mb-3 space-y-1">
          {assurance.plan.map((item) => (
            <li key={item.document_id} className="text-caption text-ink-2">
              <bdi className="text-ink">{item.filename}</bdi>{" "}
              <span aria-hidden className="inline-block rtl:-scale-x-100">
                →
              </span>{" "}
              {t(`catalog.docType.${item.doc_type}`, { defaultValue: item.doc_type })}{" "}
              <Badge tone="outline">
                {t("caseDetail.assurance.sure", {
                  value: formatPercent(item.classification_confidence),
                })}
              </Badge>{" "}
              {item.dispatched ? null : (
                <Badge tone="warning">
                  {t("caseDetail.assurance.notDispatched", { reason: item.skipped_because })}
                </Badge>
              )}
              {item.evidence.length > 0 ? (
                <span className="mt-0.5 block text-ink-2/80">
                  {t("caseDetail.assurance.matchedOn", { evidence: item.evidence.join(", ") })}
                </span>
              ) : null}
            </li>
          ))}
        </ul>
        <div className="space-y-2">
          {assurance.worker_results.map((worker) => (
            <WorkerCard key={worker.document_id} worker={worker} />
          ))}
        </div>
      </Section>

      <Section
        icon={Search}
        title={t("caseDetail.assurance.critic")}
        subtitle={t("caseDetail.assurance.criticSubtitle")}
        badge={
          disagreements.length > 0 ? (
            <Badge tone="warning">
              {t("caseDetail.assurance.disagreed", { count: disagreements.length })}
            </Badge>
          ) : (
            <Badge tone="success">
              {t("caseDetail.assurance.agreedAll", { count: assurance.critic_notes.length })}
            </Badge>
          )
        }
        defaultOpen={disagreements.length > 0}
      >
        {assurance.critic_notes.length === 0 ? (
          <p className="text-caption text-ink-2">{t("caseDetail.assurance.criticEmpty")}</p>
        ) : (
          <ul className="divide-y divide-border">
            {[...disagreements, ...assurance.critic_notes.filter((n) => n.agreed)].map((note) => (
              <CriticRow key={note.field} note={note} />
            ))}
          </ul>
        )}
      </Section>

      <Section
        icon={Search}
        title={t("caseDetail.assurance.investigation")}
        subtitle={t("caseDetail.assurance.investigationSubtitle")}
        badge={
          <Badge tone="neutral">
            {t("caseDetail.assurance.steps", { count: assurance.investigation.length })}
          </Badge>
        }
        defaultOpen={assurance.investigation.length > 0}
      >
        {assurance.investigation.length === 0 ? (
          <p className="text-caption text-ink-2">
            {t("caseDetail.assurance.investigationEmpty")}
          </p>
        ) : (
          <ol className="space-y-3">
            {assurance.investigation.map((step) => (
              <li key={step.index} className="rounded-lg border border-border bg-surface-2/50 p-3">
                <p className="text-caption text-ink-2">
                  <span className="label-caption text-ink-2">{t("caseDetail.assurance.thought")}</span>
                  <span className="mt-0.5 block text-small text-ink">{step.thought}</span>
                </p>
                <p className="mt-2 text-caption text-ink-2">
                  <span className="label-caption text-ink-2">{t("caseDetail.assurance.action")}</span>
                  <code className="mt-0.5 block text-caption text-ink" dir="ltr">
                    {step.action}
                  </code>
                </p>
                <p className="mt-2 text-caption text-ink-2">
                  <span className="label-caption text-ink-2">{t("caseDetail.assurance.observation")}</span>
                  <span
                    className={cn("mt-0.5 block text-small", step.ok ? "text-ink" : "text-danger")}
                  >
                    {step.observation}
                  </span>
                </p>
              </li>
            ))}
          </ol>
        )}
      </Section>

      <Section
        icon={Wrench}
        title={t("caseDetail.assurance.toolCalls")}
        subtitle={t("caseDetail.assurance.toolCallsSubtitle")}
        badge={
          failedCalls.length > 0 ? (
            <Badge tone="danger">
              {t("caseDetail.assurance.failedCalls", { count: failedCalls.length })}
            </Badge>
          ) : (
            <Badge tone="neutral">
              {t("caseDetail.assurance.calls", { count: assurance.tool_calls.length })}
            </Badge>
          )
        }
      >
        {assurance.tool_calls.length === 0 ? (
          <p className="text-caption text-ink-2">{t("caseDetail.assurance.noTools")}</p>
        ) : (
          <ul className="divide-y divide-border">
            {assurance.tool_calls.map((call, index) => (
              <li key={`${call.server}-${call.tool}-${index}`} className="py-1.5">
                <p className="flex flex-wrap items-center gap-1.5">
                  <code className="text-caption text-ink" dir="ltr">
                    {call.server}.{call.tool}
                  </code>
                  <Badge tone={call.ok ? "success" : "danger"}>{call.ok ? t("caseDetail.assurance.ok") : t("caseDetail.assurance.failed")}</Badge>
                  <Badge tone="outline">{formatDuration(call.duration_ms)}</Badge>
                  {call.server !== "document_store" ? (
                    <SimulatedBadge status="simulated" />
                  ) : null}
                </p>
                {call.error ? (
                  <p className="mt-0.5 text-caption text-danger">{call.error}</p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section
        icon={CheckCircle2}
        title={t("caseDetail.assurance.rules")}
        subtitle={t("caseDetail.assurance.rulesSubtitle")}
      >
        <dl className="space-y-2">
          {Object.entries(assurance.rule_packs).map(([docType, reference]) => (
            <div key={docType} className="flex items-center justify-between gap-2">
              <dt className="text-caption text-ink-2">
                {t(`catalog.docType.${docType}`, { defaultValue: docType })}
              </dt>
              <dd>
                <code className="text-caption text-ink" dir="ltr">
                  {reference}
                </code>
              </dd>
            </div>
          ))}
          {Object.entries(assurance.prompt_versions).map(([docType, version]) => (
            <div key={`prompt-${docType}`} className="flex items-center justify-between gap-2">
              <dt className="text-caption text-ink-2">
                {t("caseDetail.assurance.promptFor", {
                  docType: t(`catalog.docType.${docType}`, { defaultValue: docType }),
                })}
              </dt>
              <dd>
                <code className="text-caption text-ink" dir="ltr">
                  {version}
                </code>
              </dd>
            </div>
          ))}
          <div className="border-t border-border pt-2">
            <dt className="label-caption text-ink-2">{t("caseDetail.assurance.calibration")}</dt>
            <dd className="mt-0.5 text-caption text-ink-2">
              {assurance.calibration.fitted ? (
                t("caseDetail.assurance.calibrationFitted", {
                  count: assurance.calibration.sample_count,
                  before: formatNumber(assurance.calibration.brier_before, 3),
                  after: formatNumber(assurance.calibration.brier_after, 3),
                })
              ) : (
                t("caseDetail.assurance.calibrationNotFitted")
              )}
            </dd>
          </div>
        </dl>
      </Section>
    </div>
  );
}
