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
import type { CaseAssurance, CriticNote, GuardrailReport, WorkerResult } from "@/lib/types";
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
  const piiTypes = Object.entries(report.pii_counts);
  return (
    <div className="rounded-lg border border-border bg-surface-2/50 p-3">
      <p className="truncate text-small font-medium text-ink">{report.filename}</p>
      <div className="mt-2 space-y-1.5">
        <Verdict ok={!report.injection.attacked}>
          {report.injection.attacked
            ? `Prompt shield: ${report.injection.signals.length} suspicious pattern(s), risk ${Math.round(
                report.injection.risk * 100,
              )}%`
            : "Prompt shield: no instruction-shaped text found"}
        </Verdict>
        {report.injection.attacked ? (
          <ul className="ml-5 space-y-1">
            {report.injection.signals.slice(0, 4).map((signal, index) => (
              <li key={`${signal.kind}-${index}`} className="text-caption text-ink-2">
                <Badge tone="danger">{signal.kind}</Badge>{" "}
                <span className="break-words">{signal.excerpt}</span>
              </li>
            ))}
          </ul>
        ) : null}
        <Verdict ok={!report.safety.flagged}>
          {report.safety.flagged
            ? `Content safety: flagged (${report.safety.matches.join(", ")})`
            : "Content safety: nothing flagged"}
        </Verdict>
        <Verdict ok>
          {piiTypes.length === 0
            ? "PII tokenisation: no identifiers found"
            : `PII tokenisation: ${piiTypes
                .map(([label, count]) => `${count}× ${label}`)
                .join(", ")} replaced with tokens before logging`}
        </Verdict>
        <Verdict ok>
          {report.sanitised
            ? "Sanitiser: removed markup or invisible characters"
            : "Sanitiser: nothing to remove"}
        </Verdict>
      </div>
    </div>
  );
}

function WorkerCard({ worker }: { worker: WorkerResult }) {
  return (
    <div className="rounded-lg border border-border bg-surface-2/50 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="truncate text-small font-medium text-ink">{worker.filename}</p>
        <span className="flex items-center gap-1.5">
          <Badge tone="neutral">{worker.field_count} fields</Badge>
          <Badge tone={worker.attempts > 1 ? "warning" : "success"}>
            {worker.attempts} attempt{worker.attempts === 1 ? "" : "s"}
          </Badge>
          <Badge tone="outline">{worker.duration_ms} ms</Badge>
        </span>
      </div>

      {worker.repairs.length === 0 ? (
        <p className="mt-2 text-caption text-ink-2">
          Every value validated on the first read — no self-correction was needed.
        </p>
      ) : (
        <ul className="mt-2 space-y-1.5">
          {worker.repairs.map((repair, index) => (
            <li key={`${repair.field}-${index}`} className="text-caption text-ink-2">
              <span className="font-medium text-ink">{repair.field}</span>{" "}
              <Badge tone="outline">pass {repair.pass}</Badge>{" "}
              <Badge tone={repair.strategy === "drop" ? "danger" : "info"}>{repair.strategy}</Badge>
              <span className="mt-0.5 block">
                {repair.error}. {repair.explanation}
                {repair.after ? ` → ${repair.after}` : " → left empty"}
              </span>
            </li>
          ))}
        </ul>
      )}

      {worker.examples.length > 0 ? (
        <p className="mt-2 border-t border-border pt-2 text-caption text-ink-2">
          Few-shot examples selected for the prompt:{" "}
          {worker.examples.map((example) => example.id).join(", ")}{" "}
          <span className="text-ink-2/80">
            (selection runs in demo mode; the demo extractor makes no model call)
          </span>
        </p>
      ) : null}
    </div>
  );
}

function CriticRow({ note }: { note: CriticNote }) {
  return (
    <li className="flex items-start gap-2 py-1.5">
      {note.agreed ? (
        <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" aria-hidden />
      ) : (
        <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-danger" aria-hidden />
      )}
      <span className="min-w-0 flex-1">
        <span className="text-small text-ink">{note.field}</span>
        <span className="mt-0.5 block text-caption text-ink-2">{note.reason}</span>
      </span>
      <Badge tone="outline">{note.via === "local" ? "in-process" : note.via}</Badge>
    </li>
  );
}

export function AssurancePanel({ assurance }: { assurance: CaseAssurance }) {
  if (!assurance.available) {
    return (
      <EmptyState
        icon={Shield}
        title="No agent checkpoint for this case"
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
        title="Guardrails"
        subtitle="Prompt shield, content safety and PII tokenisation, before anything read the text"
        badge={
          blocked.length > 0 ? (
            <Badge tone="danger">{blocked.length} flagged</Badge>
          ) : (
            <Badge tone="success">all clear</Badge>
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
        title="Supervisor and workers"
        subtitle="One worker per document, dispatched in parallel, each self-correcting on its own validation errors"
        badge={<Badge tone="neutral">{dispatched.length} in parallel</Badge>}
      >
        <ul className="mb-3 space-y-1">
          {assurance.plan.map((item) => (
            <li key={item.document_id} className="text-caption text-ink-2">
              <span className="text-ink">{item.filename}</span> → {item.doc_type}{" "}
              <Badge tone="outline">
                {Math.round(item.classification_confidence * 100)}% sure
              </Badge>{" "}
              {item.dispatched ? null : (
                <Badge tone="warning">not dispatched: {item.skipped_because}</Badge>
              )}
              {item.evidence.length > 0 ? (
                <span className="mt-0.5 block text-ink-2/80">
                  matched on: {item.evidence.join(", ")}
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
        title="Critic"
        subtitle="An independent second read of every value: is it on the page, is it the right shape, is it under the right label"
        badge={
          disagreements.length > 0 ? (
            <Badge tone="warning">{disagreements.length} disagreed</Badge>
          ) : (
            <Badge tone="success">agreed on all {assurance.critic_notes.length}</Badge>
          )
        }
        defaultOpen={disagreements.length > 0}
      >
        {assurance.critic_notes.length === 0 ? (
          <p className="text-caption text-ink-2">The critic had no values to challenge.</p>
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
        title="Investigation"
        subtitle="A bounded ReAct loop: a question, a tool, an observation — for what the documents cannot answer"
        badge={<Badge tone="neutral">{assurance.investigation.length} steps</Badge>}
        defaultOpen={assurance.investigation.length > 0}
      >
        {assurance.investigation.length === 0 ? (
          <p className="text-caption text-ink-2">
            Nothing needed asking of the outside world for this case.
          </p>
        ) : (
          <ol className="space-y-3">
            {assurance.investigation.map((step) => (
              <li key={step.index} className="rounded-lg border border-border bg-surface-2/50 p-3">
                <p className="text-caption text-ink-2">
                  <span className="label-caption text-ink-2">Thought</span>
                  <span className="mt-0.5 block text-small text-ink">{step.thought}</span>
                </p>
                <p className="mt-2 text-caption text-ink-2">
                  <span className="label-caption text-ink-2">Action</span>
                  <code className="mt-0.5 block text-caption text-ink" dir="ltr">
                    {step.action}
                  </code>
                </p>
                <p className="mt-2 text-caption text-ink-2">
                  <span className="label-caption text-ink-2">Observation</span>
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
        title="Tool calls"
        subtitle="Every MCP call this case made, in order, with what came back"
        badge={
          failedCalls.length > 0 ? (
            <Badge tone="danger">{failedCalls.length} failed</Badge>
          ) : (
            <Badge tone="neutral">{assurance.tool_calls.length} calls</Badge>
          )
        }
      >
        {assurance.tool_calls.length === 0 ? (
          <p className="text-caption text-ink-2">No external tools were needed.</p>
        ) : (
          <ul className="divide-y divide-border">
            {assurance.tool_calls.map((call, index) => (
              <li key={`${call.server}-${call.tool}-${index}`} className="py-1.5">
                <p className="flex flex-wrap items-center gap-1.5">
                  <code className="text-caption text-ink" dir="ltr">
                    {call.server}.{call.tool}
                  </code>
                  <Badge tone={call.ok ? "success" : "danger"}>{call.ok ? "ok" : "failed"}</Badge>
                  <Badge tone="outline">{call.duration_ms} ms</Badge>
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
        title="Rules and calibration"
        subtitle="Which versioned rule pack judged this case, and whether its confidence went through a fitted curve"
      >
        <dl className="space-y-2">
          {Object.entries(assurance.rule_packs).map(([docType, reference]) => (
            <div key={docType} className="flex items-center justify-between gap-2">
              <dt className="text-caption text-ink-2">{docType}</dt>
              <dd>
                <code className="text-caption text-ink" dir="ltr">
                  {reference}
                </code>
              </dd>
            </div>
          ))}
          {Object.entries(assurance.prompt_versions).map(([docType, version]) => (
            <div key={`prompt-${docType}`} className="flex items-center justify-between gap-2">
              <dt className="text-caption text-ink-2">{docType} prompt</dt>
              <dd>
                <code className="text-caption text-ink" dir="ltr">
                  {version}
                </code>
              </dd>
            </div>
          ))}
          <div className="border-t border-border pt-2">
            <dt className="label-caption text-ink-2">Confidence calibration</dt>
            <dd className="mt-0.5 text-caption text-ink-2">
              {assurance.calibration.fitted ? (
                <>
                  Fitted on {assurance.calibration.sample_count} reviewed field(s). Brier score{" "}
                  {assurance.calibration.brier_before.toFixed(3)} →{" "}
                  {assurance.calibration.brier_after.toFixed(3)}.
                </>
              ) : (
                <>
                  Not fitted yet, so the numbers on this case are the extractor&rsquo;s raw
                  scores. They are shown as raw rather than presented as calibrated.
                </>
              )}
            </dd>
          </div>
        </dl>
      </Section>
    </div>
  );
}
