import {
  AlarmClock,
  Banknote,
  CircleDollarSign,
  FileStack,
  Inbox,
  Timer,
  UserCheck,
  Zap,
} from "lucide-react";
import type { DashboardKpis, Role } from "@/lib/types";
import { formatDuration, formatNumber, formatPercent, formatUsd } from "@/lib/format";
import { StatCard } from "@/components/StatCard";
import { StatCardSkeleton } from "@/components/Skeletons";

export function KpiRowSkeleton() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {[0, 1, 2, 3, 4, 5, 6].map((i) => (
        <StatCardSkeleton key={i} />
      ))}
    </div>
  );
}

interface Kpi {
  key: string;
  label: string;
  value: string;
  icon: typeof FileStack;
  deltaKey: string;
  invert?: boolean;
  hint?: string;
}

export function KpiRow({ kpis, role }: { kpis: DashboardKpis; role: Role | undefined }) {
  const all: Kpi[] = [
    {
      key: "cases_today",
      label: "Cases today",
      value: formatNumber(kpis.cases_today),
      icon: FileStack,
      deltaKey: "cases_today",
      hint: `${formatNumber(kpis.cases_total)} total`,
    },
    {
      key: "straight_through_rate",
      label: "Straight-through",
      value: formatPercent(kpis.straight_through_rate, 1),
      icon: Zap,
      deltaKey: "straight_through_rate",
      hint: "no human touched it",
    },
    {
      key: "review_rate",
      label: "Review rate",
      value: formatPercent(kpis.review_rate, 1),
      icon: UserCheck,
      deltaKey: "review_rate",
      invert: true,
      hint: "sent to a human",
    },
    {
      key: "avg_handling_ms",
      label: "Avg handling time",
      value: formatDuration(kpis.avg_handling_ms),
      icon: Timer,
      deltaKey: "avg_handling_ms",
      invert: true,
    },
    {
      key: "sla_breaches",
      label: "SLA breaches",
      value: formatNumber(kpis.sla_breaches),
      icon: AlarmClock,
      deltaKey: "sla_breaches",
      invert: true,
    },
    {
      key: "avg_cost_usd",
      label: "Avg cost / case",
      value: formatUsd(kpis.avg_cost_usd),
      icon: CircleDollarSign,
      deltaKey: "avg_cost_usd",
      invert: true,
      hint: "model + OCR",
    },
    {
      key: "open_reviews",
      label: "Open reviews",
      value: formatNumber(kpis.open_reviews),
      icon: Inbox,
      deltaKey: "open_reviews",
      invert: true,
    },
  ];

  // Reviewers lead with their own workload; everyone else leads with volume.
  const ordered =
    role === "reviewer"
      ? [...all].sort((a, b) => {
          const rank = (k: string) =>
            k === "open_reviews" ? 0 : k === "sla_breaches" ? 1 : k === "review_rate" ? 2 : 3;
          return rank(a.key) - rank(b.key);
        })
      : all;

  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {ordered.map((kpi) => (
        <StatCard
          key={kpi.key}
          label={kpi.label}
          value={kpi.value}
          icon={kpi.key === "avg_cost_usd" ? Banknote : kpi.icon}
          delta={kpis.deltas[kpi.deltaKey]}
          invertDelta={kpi.invert}
          hint={kpi.hint}
        />
      ))}
    </div>
  );
}
