import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Clock } from "lucide-react";
import type { SlaState } from "@/lib/types";
import { formatCountdown, formatDateTime, msUntil } from "@/lib/format";
import { cn } from "@/lib/cn";
import { Tooltip } from "./ui/tooltip";

const TONE: Record<SlaState, string> = {
  on_track: "text-ink-2",
  at_risk: "text-warning",
  breached: "text-danger",
  none: "text-ink-2/70",
};

const DOT: Record<SlaState, string> = {
  on_track: "bg-ink-2",
  at_risk: "bg-warning animate-[pulse-dot_1.8s_ease-in-out_infinite]",
  breached: "bg-danger",
  none: "bg-border",
};

export function SlaTimer({
  dueAt,
  state,
  className,
}: {
  dueAt: string | null;
  state: SlaState;
  className?: string;
}) {
  const { t } = useTranslation();
  const [remaining, setRemaining] = useState(() => msUntil(dueAt));

  useEffect(() => {
    setRemaining(msUntil(dueAt));
    if (!dueAt) return;
    const id = window.setInterval(() => setRemaining(msUntil(dueAt)), 30_000);
    return () => window.clearInterval(id);
  }, [dueAt]);

  if (state === "none" || remaining === null) {
    return (
      <span className={cn("text-small text-ink-2/70", className)}>
        {t("catalog.sla.none")}
      </span>
    );
  }

  const overdue = remaining < 0;
  const text = overdue
    ? t("sla.over", { time: formatCountdown(remaining) })
    : t("sla.left", { time: formatCountdown(remaining) });
  const stateLabel = t(`catalog.sla.${state}`);

  return (
    <Tooltip content={t("sla.due", { state: stateLabel, date: formatDateTime(dueAt) })}>
      <span
        className={cn("inline-flex items-center gap-1.5 text-small tabular", TONE[state], className)}
      >
        <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", DOT[state])} aria-hidden />
        <Clock className="h-3.5 w-3.5" aria-hidden />
        {text}
      </span>
    </Tooltip>
  );
}
