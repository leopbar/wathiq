import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowRight } from "lucide-react";
import { subscribeToCaseEvents } from "@/lib/api";
import { PIPELINE_NODES } from "@/lib/constants";
import type { CaseProgressEvent } from "@/lib/types";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { CopyButton } from "@/components/ui/code-block";
import { Stepper, type StepperStep } from "@/components/Stepper";

type Phase = "streaming" | "ended" | "error";

export function PipelineProgress({
  caseId,
  reference,
  threadId,
}: {
  caseId: string;
  reference: string;
  threadId: string | null;
}) {
  const { t } = useTranslation();
  const [events, setEvents] = useState<CaseProgressEvent[]>([]);
  const [phase, setPhase] = useState<Phase>("streaming");

  useEffect(() => {
    setEvents([]);
    setPhase("streaming");
    const unsubscribe = subscribeToCaseEvents(caseId, {
      onProgress: (event) => setEvents((prev) => [...prev, event]),
      onDone: () => setPhase("ended"),
      onError: () => setPhase("error"),
    });
    return unsubscribe;
  }, [caseId]);

  const latest = events.at(-1);
  const percent = latest?.percent ?? 0;

  const steps = useMemo<StepperStep[]>(() => {
    // Keep the LAST frame per node: a step can report "running" then "done".
    const seen = new Map<string, CaseProgressEvent>();
    for (const event of events) seen.set(event.node, event);
    const activeIndex = PIPELINE_NODES.findIndex((node) => node.key === latest?.node);

    return PIPELINE_NODES.map((node, index) => {
      const event = seen.get(node.key);
      let state: StepperStep["state"] = "pending";
      if (event) {
        if (event.status === "failed") state = "failed";
        // "waiting" means the graph is parked at the review gate for a person. It stays
        // waiting even after the stream closes, because nothing will move until they answer.
        else if (event.status === "waiting") state = "waiting";
        else if (event.status === "done") state = "done";
        else if (activeIndex === index && phase === "streaming") state = "active";
        else state = "done";
      } else if (activeIndex >= 0 && index < activeIndex) {
        // Earlier steps must already have run for a later one to be reporting.
        state = "done";
      }
      return {
        key: node.key,
        label: t(`pipeline.${node.key}.label`),
        description: t(`pipeline.${node.key}.description`),
        state,
        message: event?.message,
      };
    });
  }, [events, latest, phase, t]);

  const parked = steps.some((step) => step.state === "waiting");

  return (
    <Card className="overflow-hidden">
      <CardHeader
        title={t("pipelineProgress.title")}
        description={t("pipelineProgress.description", { reference })}
        action={
          <Link
            to={`/cases/${caseId}`}
            className={buttonVariants({ variant: "primary", size: "sm" })}
          >
            {t("pipelineProgress.viewCase")}
            <ArrowRight className="h-3.5 w-3.5 rtl:rotate-180" aria-hidden />
          </Link>
        }
      />

      <div className="space-y-4 p-5">
        <div className="flex items-center gap-3">
          <Progress value={percent} label={t("pipelineProgress.progress")} className="flex-1" />
          <span className="text-small font-medium text-ink tabular">{Math.round(percent)}%</span>
        </div>

        <div aria-live="polite" className="sr-only">
          {latest
            ? `${latest.node}: ${latest.message}`
            : t("pipelineProgress.waitingToStart")}
        </div>

        {phase === "error" ? (
          <p className="rounded-[var(--radius)] border border-warning/30 bg-warning-soft px-3 py-2 text-small text-warning">
            {t("pipelineProgress.streamDropped")}
          </p>
        ) : null}

        {phase === "ended" && parked ? (
          <p className="rounded-[var(--radius)] border border-warning/30 bg-warning-soft px-3 py-2 text-small text-warning">
            {t("pipelineProgress.parked")}
          </p>
        ) : null}

        {phase === "ended" && events.length === 0 ? (
          <p className="rounded-[var(--radius)] border border-border bg-surface-2 px-3 py-2 text-small text-ink-2">
            {t("pipelineProgress.noFrames")}
          </p>
        ) : null}

        <Stepper steps={steps} />

        {threadId ? (
          <div className="flex flex-wrap items-center gap-2 rounded-[var(--radius)] border border-border bg-surface-2/60 px-3 py-2">
            <Badge tone="primary">{t("pipelineProgress.thread")}</Badge>
            <code className="truncate text-caption text-ink tabular" dir="ltr">
              {threadId}
            </code>
            <span className="ms-auto">
              <CopyButton value={threadId} label={t("pipelineProgress.copyThread")} />
            </span>
          </div>
        ) : null}

        {events.length > 0 ? (
          <details className="rounded-[var(--radius)] border border-border">
            <summary className="cursor-pointer px-3 py-2 text-small text-ink-2 hover:text-ink">
              {t("pipelineProgress.rawStream", { count: events.length })}
            </summary>
            <ul className="max-h-48 space-y-1 overflow-y-auto scroll-thin border-t border-border px-3 py-2">
              {events.map((event, index) => (
                <li key={index} className="text-caption text-ink-2" dir="ltr">
                  <code>{event.node}</code> · {event.status} · {event.message}
                </li>
              ))}
            </ul>
          </details>
        ) : null}
      </div>
    </Card>
  );
}
