import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { CheckCircle2, XCircle } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { qk } from "@/lib/query";
import type { QualityRunDetail } from "@/lib/types";
import { formatDateTime, formatNumber, formatPercent } from "@/lib/format";
import { Sheet } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { ListSkeleton } from "@/components/Skeletons";
import { ErrorState } from "@/components/ErrorState";
import { EmptyState } from "@/components/EmptyState";

export function RunDrawer({
  runId,
  onOpenChange,
}: {
  runId: string | null;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useTranslation();
  const query = useQuery({
    queryKey: qk.qualityRun(runId ?? ""),
    queryFn: () => apiFetch<QualityRunDetail>(`/quality/runs/${runId}`),
    enabled: Boolean(runId),
  });

  return (
    <Sheet
      open={Boolean(runId)}
      onOpenChange={onOpenChange}
      title={t("quality.drawer.title")}
      description={t("quality.drawer.description")}
      width="42rem"
    >
      {query.isPending ? (
        <ListSkeleton rows={6} />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        <div className="space-y-4">
          <p className="text-small text-ink-2">
            {query.data.run.provenance.kind === "measured"
              ? t("quality.drawer.measured", {
                  dataset: query.data.run.provenance.dataset,
                  count: query.data.run.provenance.sample_count,
                  scope: query.data.run.provenance.scope,
                })
              : t("quality.drawer.illustrative")}
          </p>
          {query.data.run.provenance.sensitivity ? (
            <p className="text-small text-ink-2">
              {t("quality.drawer.sensitivity", {
                reason: query.data.run.provenance.sensitivity.reason,
              })}
            </p>
          ) : null}
          <dl className="grid grid-cols-2 gap-3 rounded-[var(--radius)] border border-border bg-surface-2/50 p-3 sm:grid-cols-4">
            <div>
              <dt className="label-caption text-ink-2">{t("quality.columns.band")}</dt>
              <dd className="text-small text-ink">
                <bdi>{query.data.run.band}</bdi>
              </dd>
            </div>
            <div>
              <dt className="label-caption text-ink-2">{t("quality.columns.score")}</dt>
              <dd className="text-small text-ink tabular">
                {formatPercent(query.data.run.score, 1)}
              </dd>
            </div>
            <div>
              <dt className="label-caption text-ink-2">{t("quality.drawer.result")}</dt>
              <dd className="text-small text-ink tabular">
                {t("quality.drawer.passedFailed", {
                  passed: formatNumber(query.data.run.passed),
                  failed: formatNumber(query.data.run.failed),
                })}
              </dd>
            </div>
            <div>
              <dt className="label-caption text-ink-2">{t("quality.columns.started")}</dt>
              <dd className="text-small text-ink">{formatDateTime(query.data.run.started_at)}</dd>
            </div>
          </dl>

          {query.data.cases.length === 0 ? (
            <EmptyState title={t("quality.drawer.noCases")} />
          ) : (
            <ul className="divide-y divide-border rounded-[var(--radius)] border border-border">
              {query.data.cases.map((testCase) => {
                const passed = testCase.passed;
                return (
                  <li key={testCase.id} className="px-3 py-3">
                    <div className="flex items-start gap-2">
                      {passed ? (
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden />
                      ) : (
                        <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger" aria-hidden />
                      )}
                      <div className="min-w-0 flex-1">
                        <p className="text-small font-medium text-ink">{testCase.name}</p>
                        <p className="mt-0.5 text-caption text-ink-2">{testCase.note}</p>
                      </div>
                      <Badge tone={passed ? "success" : "danger"}>{passed ? t("quality.drawer.passed") : t("quality.drawer.failed")}</Badge>
                    </div>
                    {!passed ? (
                      <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                        <div className="rounded-[var(--radius-sm)] bg-surface-2 p-2">
                          <dt className="label-caption text-ink-2">{t("quality.drawer.expected")}</dt>
                          <dd className="mt-0.5 break-words text-caption text-ink">
                            <bdi>{testCase.expected}</bdi>
                          </dd>
                        </div>
                        <div className="rounded-[var(--radius-sm)] bg-danger-soft p-2">
                          <dt className="label-caption text-danger">{t("quality.drawer.actual")}</dt>
                          <dd className="mt-0.5 break-words text-caption text-ink">
                            <bdi>{testCase.actual}</bdi>
                          </dd>
                        </div>
                      </dl>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </Sheet>
  );
}
