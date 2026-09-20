import type { LucideIcon } from "lucide-react";
import { Minus, TrendingDown, TrendingUp } from "lucide-react";
import { cn } from "@/lib/cn";
import { Card } from "./ui/card";
import { Tooltip } from "./ui/tooltip";

export function DeltaChip({
  delta,
  invert = false,
  suffix = "vs last week",
}: {
  delta: number | undefined;
  /** true when a rise is bad (SLA breaches, cost). */
  invert?: boolean;
  suffix?: string;
}) {
  if (delta === undefined || Number.isNaN(delta)) return null;

  const flat = Math.abs(delta) < 0.0005;
  const up = delta > 0;
  const good = flat ? null : invert ? !up : up;
  const Icon = flat ? Minus : up ? TrendingUp : TrendingDown;

  return (
    <Tooltip content={`${(delta * 100).toFixed(1)}% ${suffix}`}>
      <span
        className={cn(
          "inline-flex items-center gap-1 rounded-full border px-1.5 py-0.5 text-caption font-medium tabular",
          good === null && "border-border bg-surface-2 text-ink-2",
          good === true && "border-success/30 bg-success-soft text-success",
          good === false && "border-danger/30 bg-danger-soft text-danger",
        )}
      >
        <Icon className="h-3 w-3" aria-hidden />
        {flat ? "0%" : `${up ? "+" : ""}${(delta * 100).toFixed(1)}%`}
      </span>
    </Tooltip>
  );
}

export function StatCard({
  label,
  value,
  icon: Icon,
  delta,
  invertDelta,
  hint,
  className,
}: {
  label: string;
  value: string;
  icon: LucideIcon;
  delta?: number;
  invertDelta?: boolean;
  hint?: string;
  className?: string;
}) {
  return (
    <Card className={cn("p-4", className)}>
      <div className="flex items-start justify-between gap-2">
        <p className="label-caption text-ink-2">{label}</p>
        <span className="flex h-7 w-7 items-center justify-center rounded-[var(--radius-sm)] bg-surface-2 text-ink-2">
          <Icon className="h-3.5 w-3.5" aria-hidden />
        </span>
      </div>
      <p className="mt-2.5 text-display font-semibold tracking-tight text-ink tabular">{value}</p>
      <div className="mt-2.5 flex items-center gap-2">
        <DeltaChip delta={delta} invert={invertDelta} />
        {hint ? <span className="truncate text-caption text-ink-2">{hint}</span> : null}
      </div>
    </Card>
  );
}
