import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Play } from "lucide-react";
import { apiFetch, buildQuery } from "@/lib/api";
import { qk } from "@/lib/query";
import type { Page, QualityCalibration, QualityRun, QualitySummary } from "@/lib/types";
import { formatDateTime, formatDuration, formatPercent, parseDate } from "@/lib/format";
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
  const queryClient = useQueryClient();
  const { role } = useAuth();
  const mayRun = can(role, "quality.run");

  const [band, setBand] = useState("all");
  const [openRunId, setOpenRunId] = useState<string | null>(null);

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

  const startRun = useMutation({
    mutationFn: (target: string) =>
      apiFetch<QualityRun>("/quality/runs", {
        method: "POST",
        body: JSON.stringify({ band: target }),
      }),
    onSuccess: (run) => {
      toast.success("Evaluation started", {
        description: `Band “${run.band}” is running. Results land in the history below.`,
      });
      void queryClient.invalidateQueries({ queryKey: ["quality"] });
    },
    onError: (error) =>
      toast.error("Evaluation could not start", { description: describeError(error).message }),
  });

  const columns: Column<QualityRun>[] = [
    {
      key: "band",
      header: "Band",
      cell: (row) => <span className="text-small font-medium text-ink">{row.band}</span>,
    },
    {
      key: "score",
      header: "Score",
      cell: (row) => (
        <Badge tone={row.score >= 0.9 ? "success" : row.score >= 0.75 ? "warning" : "danger"}>
          {formatPercent(row.score, 1)}
        </Badge>
      ),
    },
    {
      key: "result",
      header: "Passed / failed",
      cell: (row) => (
        <span className="text-small tabular">
          <span className="text-success">{row.passed}</span>
          <span className="text-ink-2"> / </span>
          <span className={row.failed > 0 ? "text-danger" : "text-ink-2"}>{row.failed}</span>
        </span>
      ),
    },
    {
      key: "duration",
      header: "Duration",
      cell: (row) => {
        const started = parseDate(row.started_at);
        const finished = parseDate(row.finished_at);
        return (
          <span className="text-small text-ink-2">
            {started && finished ? formatDuration(finished.getTime() - started.getTime()) : "running"}
          </span>
        );
      },
    },
    {
      key: "triggered_by",
      header: "Triggered by",
      cell: (row) => <span className="text-small text-ink-2">{row.triggered_by}</span>,
    },
    {
      key: "commit",
      header: "Commit",
      cell: (row) => (
        <code className="text-caption text-ink-2" dir="ltr">
          {row.commit_sha.slice(0, 8)}
        </code>
      ),
    },
    {
      key: "started",
      header: "Started",
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
      Run evaluation{band !== "all" ? `: ${band}` : ""}
    </Button>
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title="Quality Lab"
        description="Five evaluation bands, a regression history, and the calibration curve behind every confidence number in the product."
        actions={
          <>
            {summary.data ? (
              <Badge tone={summary.data.overall_score >= 0.9 ? "success" : "warning"}>
                Overall {formatPercent(summary.data.overall_score, 1)}
              </Badge>
            ) : null}
            {mayRun ? (
              runButton
            ) : (
              <Tooltip content="Supervisors and administrators can start evaluation runs.">
                <span className="inline-flex">{runButton}</span>
              </Tooltip>
            )}
          </>
        }
      />

      {summary.isPending ? (
        <BandCardsSkeleton />
      ) : summary.isError ? (
        <Card>
          <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />
        </Card>
      ) : summary.data.bands.length === 0 ? (
        <Card>
          <EmptyState
            title="No evaluation bands configured"
            description="Bands are seeded with the golden dataset in M5."
          />
        </Card>
      ) : (
        <BandCards bands={summary.data.bands} selected={band} onSelect={setBand} />
      )}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-h2 font-semibold text-ink">Regression history</h2>
              <p className="text-small text-ink-2">
                {band === "all" ? "All bands" : `Filtered to “${band}”`} · newest first.
              </p>
            </div>
            {band !== "all" ? (
              <Button variant="ghost" size="sm" onClick={() => setBand("all")}>
                Clear filter
              </Button>
            ) : null}
          </div>

          <DataTable
            caption="Evaluation runs"
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
                <span className="font-medium text-ink">{row.band}</span>
                <Badge tone={row.failed > 0 ? "danger" : "success"}>
                  {formatPercent(row.score, 1)}
                </Badge>
              </div>
            )}
            empty={
              <EmptyState
                title="No runs recorded"
                description="Start an evaluation to build the regression history."
                action={mayRun ? runButton : undefined}
              />
            }
          />
        </div>

        <Card className="h-fit overflow-hidden">
          <CardHeader
            title="Confidence calibration"
            description="Predicted confidence versus observed accuracy."
            action={
              calibration.data ? (
                <div className="flex gap-1.5">
                  <Badge tone="outline">ECE {calibration.data.ece.toFixed(3)}</Badge>
                  <Badge tone="outline">Brier {calibration.data.brier.toFixed(3)}</Badge>
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
              title="No calibration data"
              description="The calibration model is fitted on the golden set."
            />
          ) : (
            <div className="p-4">
              <CalibrationChart data={calibration.data} />
              <p className="mt-3 text-caption leading-4 text-ink-2">
                Points on the dashed line mean a stated 80% is right 80% of the time. Points below
                the line mean the system is overconfident — that is what the calibration step in the
                pipeline corrects before any confidence reaches a reviewer.
              </p>
            </div>
          )}
        </Card>
      </div>

      <RunDrawer runId={openRunId} onOpenChange={(open) => !open && setOpenRunId(null)} />
    </div>
  );
}
