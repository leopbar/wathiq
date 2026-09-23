import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, FilePlus2, RefreshCw } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { qk } from "@/lib/query";
import type { DashboardCharts, DashboardKpis } from "@/lib/types";
import { formatNumber } from "@/lib/format";
import { useAuth } from "@/auth/useAuth";
import { can } from "@/auth/roles";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { ChartSkeleton } from "@/components/Skeletons";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { VolumeChart } from "@/components/charts/VolumeChart";
import { StatusDonut } from "@/components/charts/StatusDonut";
import { ConfidenceHistogram } from "@/components/charts/ConfidenceHistogram";
import { HandlingTimeChart } from "@/components/charts/HandlingTimeChart";
import { KpiRow, KpiRowSkeleton } from "./dashboard/KpiRow";
import { RoleSummary } from "./dashboard/RoleSummary";

function ChartCard({
  title,
  description,
  isPending,
  isError,
  error,
  onRetry,
  children,
  height = 260,
}: {
  title: string;
  description?: string;
  isPending: boolean;
  isError: boolean;
  error?: unknown;
  onRetry: () => void;
  children: ReactNode;
  height?: number;
}) {
  return (
    <Card className="overflow-hidden">
      <CardHeader title={title} description={description} />
      {isPending ? (
        <ChartSkeleton height={height} />
      ) : isError ? (
        <ErrorState error={error} onRetry={onRetry} />
      ) : (
        <div className="p-4 pt-5">{children}</div>
      )}
    </Card>
  );
}

export default function Dashboard() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const firstName = user
    ? (i18n.language.startsWith("ar") && user.full_name_ar
        ? user.full_name_ar
        : user.full_name
      ).split(" ")[0]
    : t("dashboard.there");

  const kpis = useQuery({
    queryKey: qk.kpis,
    queryFn: () => apiFetch<DashboardKpis>("/dashboard/kpis"),
  });
  const charts = useQuery({
    queryKey: qk.charts,
    queryFn: () => apiFetch<DashboardCharts>("/dashboard/charts"),
  });

  const refreshAll = () => {
    void kpis.refetch();
    void charts.refetch();
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("dashboard.greeting", { name: firstName })}
        description={t("dashboard.description")}
        actions={
          <>
            {user ? <Badge tone="primary">{t(`roles.${user.role}`)}</Badge> : null}
            <Button variant="secondary" size="sm" onClick={refreshAll}>
              <RefreshCw className="h-3.5 w-3.5" aria-hidden />
              {t("common.refresh")}
            </Button>
            {can(user?.role, "case.create") ? (
              <Link to="/cases/new" className={buttonVariants({ variant: "primary", size: "sm" })}>
                <FilePlus2 className="h-3.5 w-3.5" aria-hidden />
                {t("nav.newCase")}
              </Link>
            ) : null}
          </>
        }
      />

      {kpis.isPending ? (
        <KpiRowSkeleton />
      ) : kpis.isError ? (
        <Card>
          <ErrorState
            error={kpis.error}
            onRetry={() => void kpis.refetch()}
            title={t("dashboard.kpiError")}
          />
        </Card>
      ) : (
        <KpiRow kpis={kpis.data} role={user?.role} />
      )}

      <RoleSummary role={user?.role} />

      <div className="grid gap-4 xl:grid-cols-3">
        <div className="xl:col-span-2">
          <ChartCard
            title={t("dashboard.caseVolume")}
            description={t("dashboard.caseVolumeDescription")}
            isPending={charts.isPending}
            isError={charts.isError}
            error={charts.error}
            onRetry={() => void charts.refetch()}
          >
            {charts.data && charts.data.volume_by_day.length > 0 ? (
              <VolumeChart data={charts.data.volume_by_day} />
            ) : (
              <EmptyState
                title={t("dashboard.noVolume")}
                description={t("dashboard.noVolumeDescription")}
              />
            )}
          </ChartCard>
        </div>

        <ChartCard
          title={t("dashboard.statusSplit")}
          description={t("dashboard.statusSplitDescription")}
          isPending={charts.isPending}
          isError={charts.isError}
          error={charts.error}
          onRetry={() => void charts.refetch()}
        >
          {charts.data && charts.data.status_split.length > 0 ? (
            <StatusDonut data={charts.data.status_split} />
          ) : (
            <EmptyState title={t("dashboard.noCases")} />
          )}
        </ChartCard>

        <ChartCard
          title={t("dashboard.fieldConfidence")}
          description={t("dashboard.fieldConfidenceDescription")}
          height={240}
          isPending={charts.isPending}
          isError={charts.isError}
          error={charts.error}
          onRetry={() => void charts.refetch()}
        >
          {charts.data && charts.data.confidence_histogram.length > 0 ? (
            <ConfidenceHistogram data={charts.data.confidence_histogram} />
          ) : (
            <EmptyState title={t("dashboard.noExtractions")} />
          )}
        </ChartCard>

        <ChartCard
          title={t("dashboard.handlingTime")}
          description={t("dashboard.handlingTimeDescription")}
          height={240}
          isPending={charts.isPending}
          isError={charts.isError}
          error={charts.error}
          onRetry={() => void charts.refetch()}
        >
          {charts.data && charts.data.handling_time_by_day.length > 0 ? (
            <HandlingTimeChart data={charts.data.handling_time_by_day} />
          ) : (
            <EmptyState title={t("dashboard.noTimings")} />
          )}
        </ChartCard>

        <Card className="overflow-hidden">
          <CardHeader
            title={t("dashboard.topFindings")}
            description={t("dashboard.topFindingsDescription")}
          />
          {charts.isPending ? (
            <ChartSkeleton height={240} />
          ) : charts.isError ? (
            <ErrorState error={charts.error} onRetry={() => void charts.refetch()} />
          ) : charts.data.top_findings.length === 0 ? (
            <EmptyState title={t("dashboard.noFindings")} />
          ) : (
            <ul className="divide-y divide-border">
              {charts.data.top_findings.slice(0, 6).map((finding) => (
                <li key={finding.code} className="flex items-start gap-3 px-5 py-3">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-small font-medium text-ink">{finding.title}</p>
                    <code className="text-caption text-ink-2">{finding.code}</code>
                  </div>
                  <span className="text-body font-semibold text-ink tabular">
                    {formatNumber(finding.count)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
