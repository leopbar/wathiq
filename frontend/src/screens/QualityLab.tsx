import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Play } from "lucide-react";
import { apiFetch, apiUrl, getToken, buildQuery } from "@/lib/api";
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
  const download = useMutation({
    mutationFn: async (kind: "golden" | "regressions") => {
      const response = await fetch(apiUrl(kind === "golden" ? "/quality/dataset" : "/quality/regressions/export"), {
        headers: { Authorization: `Bearer ${getToken()}` },
      });
      if (!response.ok) throw new Error("Dataset download failed");
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
        toast.success("Confidence curve refitted", {
          description: `Fitted on ${result.curve.sample_count} reviewed field(s). Brier ${result.curve.brier_before.toFixed(3)} → ${result.curve.brier_after.toFixed(3)}.`,
        });
      } else {
          toast.info("Fit was not accepted", {
          description:
            result.curve.sample_count > 0
              ? `${result.curve.sample_count} reviewed field(s). The fit requires enough examples of both outcomes and must improve the training Brier score. Confidence stays raw.`
              : "No reviewed fields yet. Confidence stays raw until reviewers have decided some cases.",
        });
      }
      void queryClient.invalidateQueries({ queryKey: ["quality"] });
      void queryClient.invalidateQueries({ queryKey: qk.assurance });
    },
    onError: (error) =>
      toast.error("Refit failed", { description: describeError(error).message }),
  });

  const startRun = useMutation({
    mutationFn: (target: string) =>
      apiFetch<{ runs: QualityRun[] }>("/quality/runs", {
        method: "POST",
        body: JSON.stringify({ band: target }),
      }),
    onSuccess: ({ runs }) => {
      const failed = runs.reduce((total, run) => total + run.failed, 0);
      toast[failed ? "warning" : "success"]("Evaluation finished", {
        description: `${runs.length} band(s), ${runs.reduce((total, run) => total + run.passed + run.failed, 0)} checks, ${failed} failed.`,
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
      cell: (row) => <span className="text-small font-medium text-ink">{row.band}{row.provenance.kind !== "measured" ? " · illustrative" : ""}</span>,
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

      <Card className="flex flex-wrap items-center justify-between gap-3 p-4">
        <div className="text-small text-ink-2">
          <p>50 synthetic documents · 5 quality conditions · English and bilingual Arabic labels.</p>
          <p>Blurry scans test abstention. Scores are diagnostic checks, not production accuracy.</p>
          <p>{summary.data?.regression_cases ?? 0} saved reviewer corrections.</p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="secondary" disabled={download.isPending} onClick={() => download.mutate("regressions")}>Export corrections</Button>
          <Button size="sm" variant="secondary" loading={download.isPending} onClick={() => download.mutate("golden")}>Download golden set</Button>
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
                <div className="flex flex-wrap items-center gap-1.5">
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
                description="The calibration model is fitted on reviewer outcomes."
            />
          ) : (
            <div className="p-4">
              <CalibrationChart data={calibration.data} />
              <div className="mt-3 space-y-2 text-caption leading-4 text-ink-2">
                <p>{calibration.data.sample_count} reviewed fields. {calibration.data.metric_scope}</p>
                <p>MLflow: {calibration.data.tracking.status}. {calibration.data.tracking.reason}</p>
                {calibration.data.tracking.run_id ? <a className="text-primary underline" href={`http://localhost:5001/#/experiments/${calibration.data.tracking.experiment_id}/runs/${calibration.data.tracking.run_id}`} target="_blank" rel="noreferrer">Open local MLflow experiment</a> : null}
                <p>
                  Points on the dashed line mean a stated 80% is right 80% of the time. Points
                  below the line mean the system is overconfident — that is what the calibration
                  step corrects before any confidence reaches a reviewer.
                </p>
                <div className="rounded-lg border border-border bg-surface-2/60 p-2.5">
                  <span className="font-medium text-ink">
                    {calibration.data.curve.fitted ? "Curve fitted" : "Curve not fitted yet"}
                  </span>
                  {calibration.data.curve.fitted ? (
                    <>
                      {" "}
                      on {calibration.data.curve.sample_count} reviewed field(s). Brier{" "}
                      {calibration.data.curve.brier_before.toFixed(3)} →{" "}
                      {calibration.data.curve.brier_after.toFixed(3)}. {calibration.data.method}.
                    </>
                  ) : (
                    <>
                      {" "}
                      — the confidence shown across the product is the extractor&rsquo;s raw
                      score, labelled as raw rather than presented as calibrated.{" "}
                      {calibration.data.curve.sample_count > 0
                        ? `${calibration.data.curve.sample_count} reviewed field(s) so far.`
                        : "No reviewer decisions to learn from yet."}
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
                        {refit.isPending ? "Refitting…" : "Refit curve"}
                      </Button>
                      <span className="text-ink-2">
                        Fits again on every decision reviewers have made since.
                      </span>
                    </span>
                  ) : null}
                </div>
                <p>
                  <span className="font-medium text-ink">Where the ground truth comes from:</span>{" "}
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
