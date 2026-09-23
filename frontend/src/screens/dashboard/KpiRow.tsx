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
import { useTranslation } from "react-i18next";
import type { DashboardKpis, Role } from "@/lib/types";
import { formatDuration, formatNumber, formatPercent, formatUsd } from "@/lib/format";
import { StatCard } from "@/components/StatCard";
import { StatCardSkeleton } from "@/components/Skeletons";

/** The accessible name of the KPI block. A landmark for screen readers, and the anchor the
 *  end-to-end tests use so "Straight-through" means the KPI card and not a chart legend. */
export const KPI_REGION_LABEL = "Key performance indicators";

export function KpiRowSkeleton() {
  const { t } = useTranslation();
  return (
    <section
      aria-label={t("dashboard.kpiRegion")}
      className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"
    >
      {[0, 1, 2, 3, 4, 5, 6].map((i) => (
        <StatCardSkeleton key={i} />
      ))}
    </section>
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
  const { t } = useTranslation();
  const all: Kpi[] = [
    {
      key: "cases_today",
      label: t("dashboard.kpis.casesToday"),
      value: formatNumber(kpis.cases_today),
      icon: FileStack,
      deltaKey: "cases_today",
      hint: t("dashboard.kpis.total", { count: formatNumber(kpis.cases_total) }),
    },
    {
      key: "straight_through_rate",
      label: t("dashboard.kpis.straightThrough"),
      value: formatPercent(kpis.straight_through_rate, 1),
      icon: Zap,
      deltaKey: "straight_through_rate",
      hint: t("dashboard.kpis.noHuman"),
    },
    {
      key: "review_rate",
      label: t("dashboard.kpis.reviewRate"),
      value: formatPercent(kpis.review_rate, 1),
      icon: UserCheck,
      deltaKey: "review_rate",
      invert: true,
      hint: t("dashboard.kpis.sentToHuman"),
    },
    {
      key: "avg_handling_ms",
      label: t("dashboard.kpis.avgHandling"),
      value: formatDuration(kpis.avg_handling_ms),
      icon: Timer,
      deltaKey: "avg_handling_ms",
      invert: true,
    },
    {
      key: "sla_breaches",
      label: t("dashboard.kpis.slaBreaches"),
      value: formatNumber(kpis.sla_breaches),
      icon: AlarmClock,
      deltaKey: "sla_breaches",
      invert: true,
    },
    {
      key: "avg_cost_usd",
      label: t("dashboard.kpis.avgCost"),
      value: formatUsd(kpis.avg_cost_usd),
      icon: CircleDollarSign,
      deltaKey: "avg_cost_usd",
      invert: true,
      hint: t("dashboard.kpis.modelOcr"),
    },
    {
      key: "open_reviews",
      label: t("dashboard.kpis.openReviews"),
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
    <section
      aria-label={t("dashboard.kpiRegion")}
      className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"
    >
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
    </section>
  );
}
