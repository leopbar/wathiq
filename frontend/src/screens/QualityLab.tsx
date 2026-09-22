import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { Play } from "lucide-react";
import { apiFetch, apiUrl, getToken, buildQuery } from "@/lib/api";
import { qk } from "@/lib/query";
import type { Page, QualityCalibration, QualityRun, QualitySummary } from "@/lib/types";
import {
  formatDateTime,
  formatDuration,
  formatNumber,
  formatPercent,
  parseDate,
} from "@/lib/format";
import { useAuth } from "@/auth/useAuth";
import { can } from "@/auth/roles";
import { describeError, ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { DataTable, type Column } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { ChartSkeleton } from "@/components/Skeletons";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { CalibrationChart } from "@/components/charts/CalibrationChart";
import { BandCards, BandCardsSkeleton } from "./quality/BandCards";
import { RunDrawer } from "./quality/RunDrawer";

export default function QualityLab() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { role } = useAuth();
  const mayRun = can(role, "quality.run");

  const [band, setBand] = useState("all");
  const [openRunId, setOpenRunId] = useState<string | null>(null);
  const download = useMutation({
    mutationFn: async (kind: "golden" | "regressions") => {
      const response = await fetch(apiUrl(kind === "golden" ? "/quality/dataset" : "/quality/regressions/export"), {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!response.ok) throw new Error(t("quality.downloadFailed"));
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      link.download = kind === "golden" ? "wathiq-golden.zip" : "regressions.json";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    },
    onError: (error) => toast.error(error.message),
  });

  const summary = useQuery({
    queryKey: qk.qualitySummary,
    queryFn: () => apiFetch<QualitySummary>("/quality/summary"),
  });

  const runs = useQuery({
    queryKey: qk.qualityRuns(band),
    queryFn: () =>
      apiFetch<Page<QualityRun>>(
        `/quality/runs${buildQuery({ band: band === "all" ? "" : band, size: 20 })}`,
      ),
  });

  const calibration = useQuery({
    queryKey: qk.calibration,
    queryFn: () => apiFetch<QualityCalibration>("/quality/calibration"),
  });

  // Refitting is cheap and its training data grows every time a reviewer decides something,
  // so it is an action on this page rather than a scheduled job nobody can see.
  const refit = useMutation({
    mutationFn: () =>
      apiFetch<QualityCalibration>("/quality/calibration/refit", { method: "POST" }),
    onSuccess: (result) => {
      if (result.curve.fitted) {
        toast.success(t("quality.refitted"), {
          description: t("quality.refittedDescription", {
            count: result.curve.sample_count,
            before: formatNumber(result.curve.brier_before, 3),
            after: formatNumber(result.curve.brier_after, 3),
          }),
        });
      } else {
        toast.info(t("quality.fitRejected"), {
          description:
            result.curve.sample_count > 0
              ? t("quality.fitRejectedDescription", { count: result.curve.sample_count })
              : t("quality.fitNoData"),
        });
      }
      void queryClient.invalidateQueries({ queryKey: ["quality"] });
      void queryClient.invalidateQueries({ queryKey: qk.assurance });
    },
    onError: (error) =>
      toast.error(t("quality.refitFailed"), { description: describeError(error).message }),
  });

  const startRun = useMutation({
    mutationFn: (target: string) =>
      apiFetch<{ runs: QualityRun[] }>("/quality/runs", {
        method: "POST",
        body: JSON.stringify({ band: target }),
      }),
    onSuccess: ({ runs }) => {
      const failed = runs.reduce((total, run) => total + run.failed, 0);
      toast[failed ? "warning" : "success"](t("quality.finished"), {
        description: t("quality.finishedDescription", {
          bands: runs.length,
          checks: runs.reduce((total, run) => total + run.passed + run.failed, 0),
          failed,
        }),
      });
      void queryClient.invalidateQueries({ queryKey: ["quality"] });
    },
    onError: (error) =>
      toast.error(t("quality.startError"), { description: describeError(error).message }),
  });

  const columns: Column<QualityRun>[] = [
    {
      key: "band",
      header: t("quality.columns.band"),
      cell: (row) => (
        <span className="text-small font-medium text-ink">
          <bdi>{row.band}</bdi>
          {row.provenance.kind !== "measured" ? ` · ${t("quality.illustrative")}` : ""}
        </span>
      ),
    },
    {
      key: "score",
      header: t("quality.columns.score"),
      cell: (row) => (
        <Badge tone={row.score >= 0.9 ? "success" : row.score >= 0.75 ? "warning" : "danger"}>
          {formatPercent(row.score, 1)}
        </Badge>
      ),
    },
    {
      key: "result",
      header: t("quality.columns.result"),
      cell: (row) => (
        <span className="text-small tabular">
          <bdi>
            <span className="text-success">{formatNumber(row.passed)}</span>
            <span className="text-ink-2"> / </span>
            <span className={row.failed > 0 ? "text-danger" : "text-ink-2"}>
              {formatNumber(row.failed)}
            </span>
          </bdi>
        </span>
      ),
    },
    {
      key: "duration",
      header: t("quality.columns.duration"),
      cell: (row) => {
        const started = parseDate(row.started_at);
        const finished = parseDate(row.finished_at);
        return (
          <span className="text-small text-ink-2">
            {started && finished ? formatDuration(finished.getTime() - started.getTime()) : t("quality.running")}
          </span>
        );
      },
    },
    {
      key: "triggered_by",
      header: t("quality.columns.triggeredBy"),
      cell: (row) => <span className="text-small text-ink-2">{row.triggered_by}</span>,
    },
    {
      key: "commit",
      header: t("quality.columns.commit"),
      cell: (row) => (
        <code className="text-caption text-ink-2" dir="ltr">
          {row.commit_sha.slice(0, 8)}
        </code>
      ),
    },
    {
      key: "started",
      header: t("quality.columns.started"),
      cell: (row) => (
        <span className="text-small text-ink-2">{formatDateTime(row.started_at)}</span>
      ),
    },
  ];

  const runButton = (
    <Button
      variant="primary"
      size="sm"
      disabled={!mayRun}
      loading={startRun.isPending}
      onClick={() => startRun.mutate(band)}
    >
      <Play className="h-3.5 w-3.5" aria-hidden />
      {band !== "all" ? t("quality.runBand", { band }) : t("quality.run")}
    </Button>
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title={t("nav.quality")}
        description={t("quality.description")}
        actions={
          <>
            {summary.data ? (
              <Badge tone={summary.data.overall_score >= 0.9 ? "success" : "warning"}>
                {t("quality.overall", { score: formatPercent(summary.data.overall_score, 1) })}
              </Badge>
            ) : null}
            {mayRun ? (
              runButton
            ) : (
              <Tooltip content={t("quality.runForbidden")}>
                <span className="inline-flex">{runButton}</span>
              </Tooltip>
            )}
          </>
        }
      />

      <Card className="flex flex-wrap items-center justify-between gap-3 p-4">
        <div className="text-small text-ink-2">
          <p>{t("quality.datasetLine1")}</p>
          <p>{t("quality.datasetLine2")}</p>
          <p>{t("quality.savedCorrections", { count: summary.data?.regression_cases ?? 0 })}</p>
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="secondary"
            disabled={download.isPending}
            onClick={() => download.mutate("regressions")}
          >
            {t("quality.exportCorrections")}
          </Button>
          <Button
            size="sm"
            variant="secondary"
            loading={download.isPending}
            onClick={() => download.mutate("golden")}
          >
            {t("quality.downloadGolden")}
          </Button>
        </div>
      </Card>

      {summary.isPending ? (
        <BandCardsSkeleton />
      ) : summary.isError ? (
        <Card>
          <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />
        </Card>
      ) : summary.data.bands.length === 0 ? (
        <Card>
          <EmptyState
            title={t("quality.noBands")}
            description={t("quality.noBandsDescription")}
          />
        </Card>
      ) : (
        <BandCards bands={summary.data.bands} selected={band} onSelect={setBand} />
      )}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-h2 font-semibold text-ink">{t("quality.history")}</h2>
              <p className="text-small text-ink-2">
                {band === "all" ? t("quality.allBands") : t("quality.filteredTo", { band })} ·{" "}
                {t("quality.newestFirst")}
              </p>
            </div>
            {band !== "all" ? (
              <Button variant="ghost" size="sm" onClick={() => setBand("all")}>
                {t("quality.clearFilter")}
              </Button>
            ) : null}
          </div>

          <DataTable
            caption={t("quality.runsCaption")}
            columns={columns}
            rows={runs.data?.items ?? []}
            rowKey={(row) => row.id}
            isPending={runs.isPending}
            isError={runs.isError}
            error={runs.error}
            onRetry={() => void runs.refetch()}
            onRowClick={(row) => setOpenRunId(row.id)}
            cardTitle={(row) => (
              <div className="flex items-center justify-between gap-2">
                <bdi className="font-medium text-ink">{row.band}</bdi>
                <Badge tone={row.failed > 0 ? "danger" : "success"}>
                  {formatPercent(row.score, 1)}
                </Badge>
              </div>
            )}
            empty={
              <EmptyState
                title={t("quality.noRuns")}
                description={t("quality.noRunsDescription")}
                action={mayRun ? runButton : undefined}
              />
            }
          />
        </div>

        <Card className="h-fit overflow-hidden">
          <CardHeader
            title={t("caseDetail.assurance.calibration")}
            description={t("quality.calibrationDescription")}
            action={
              calibration.data ? (
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge tone="outline">
                    <bdi>ECE {formatNumber(calibration.data.ece, 3)}</bdi>
                  </Badge>
                  <Badge tone="outline">
                    <bdi>Brier {formatNumber(calibration.data.brier, 3)}</bdi>
                  </Badge>
                </div>
              ) : null
            }
          />
          {calibration.isPending ? (
            <ChartSkeleton height={280} />
          ) : calibration.isError ? (
            <ErrorState error={calibration.error} onRetry={() => void calibration.refetch()} />
          ) : calibration.data.points.length === 0 ? (
            <EmptyState
              title={t("quality.noCalibration")}
              description={t("quality.noCalibrationDescription")}
            />
          ) : (
            <div className="p-4">
              <CalibrationChart data={calibration.data} />
              <div className="mt-3 space-y-2 text-caption leading-4 text-ink-2">
                <p>
                  {t("quality.reviewedFields", { count: calibration.data.sample_count })}{" "}
                  {calibration.data.metric_scope}
                </p>
                <p>
                  MLflow: <bdi>{calibration.data.tracking.status}</bdi>. {calibration.data.tracking.reason}
                </p>
                {calibration.data.tracking.run_id ? (
                  <a
                    className="text-primary underline"
                    href={`http://localhost:5001/#/experiments/${calibration.data.tracking.experiment_id}/runs/${calibration.data.tracking.run_id}`}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {t("quality.openMlflow")}
                  </a>
                ) : null}
                <p>
                  {t("quality.calibrationExplain")}
                </p>
                <div className="rounded-lg border border-border bg-surface-2/60 p-2.5">
                  <span className="font-medium text-ink">
                    {calibration.data.curve.fitted
                      ? t("quality.curveFitted")
                      : t("quality.curveNotFitted")}
                  </span>
                  {calibration.data.curve.fitted ? (
                    <>
                      {" "}
                      {t("quality.curveFittedDetail", {
                        count: calibration.data.curve.sample_count,
                        before: formatNumber(calibration.data.curve.brier_before, 3),
                        after: formatNumber(calibration.data.curve.brier_after, 3),
                      })}{" "}
                      {calibration.data.method}.
                    </>
                  ) : (
                    <>
                      {" "}
                      {t("quality.curveRaw")}{" "}
                      {calibration.data.curve.sample_count > 0
                        ? t("quality.soFar", { count: calibration.data.curve.sample_count })
                        : t("quality.noDecisions")}
                    </>
                  )}
                  {mayRun ? (
                    <span className="mt-2 flex items-center gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => refit.mutate()}
                        disabled={refit.isPending}
                      >
                        {refit.isPending ? t("quality.refitting") : t("quality.refit")}
                      </Button>
                      <span className="text-ink-2">
                        {t("quality.refitNote")}
                      </span>
                    </span>
                  ) : null}
                </div>
                <p>
                  <span className="font-medium text-ink">{t("quality.groundTruth")}</span>{" "}
                  {calibration.data.ground_truth}
                </p>
              </div>
            </div>
          )}
        </Card>
      </div>

      <RunDrawer runId={openRunId} onOpenChange={(open) => !open && setOpenRunId(null)} />
    </div>
  );
}
