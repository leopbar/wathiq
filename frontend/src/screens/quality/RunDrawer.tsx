import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { qk } from "@/lib/query";
import type { QualityRunDetail } from "@/lib/types";
import { formatDateTime, formatPercent } from "@/lib/format";
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
  const query = useQuery({
    queryKey: qk.qualityRun(runId ?? ""),
    queryFn: () => apiFetch<QualityRunDetail>(`/quality/runs/${runId}`),
    enabled: Boolean(runId),
  });

  return (
    <Sheet
      open={Boolean(runId)}
      onOpenChange={onOpenChange}
      title="Evaluation run"
      description="Every case in the run, with what was expected and what the system produced."
      width="42rem"
    >
      {query.isPending ? (
        <ListSkeleton rows={6} />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : (
        <div className="space-y-4">
          <dl className="grid grid-cols-2 gap-3 rounded-[var(--radius)] border border-border bg-surface-2/50 p-3 sm:grid-cols-4">
            <div>
              <dt className="label-caption text-ink-2">Band</dt>
              <dd className="text-small text-ink">{query.data.run.band}</dd>
            </div>
            <div>
              <dt className="label-caption text-ink-2">Score</dt>
              <dd className="text-small text-ink tabular">
                {formatPercent(query.data.run.score, 1)}
              </dd>
            </div>
            <div>
              <dt className="label-caption text-ink-2">Result</dt>
              <dd className="text-small text-ink tabular">
                {query.data.run.passed} passed · {query.data.run.failed} failed
              </dd>
            </div>
            <div>
              <dt className="label-caption text-ink-2">Started</dt>
              <dd className="text-small text-ink">{formatDateTime(query.data.run.started_at)}</dd>
            </div>
          </dl>

          {query.data.cases.length === 0 ? (
            <EmptyState title="No cases in this run" />
          ) : (
            <ul className="divide-y divide-border rounded-[var(--radius)] border border-border">
              {query.data.cases.map((testCase) => {
                const passed = testCase.status === "passed";
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
                      <Badge tone={passed ? "success" : "danger"}>{testCase.status}</Badge>
                    </div>
                    {!passed ? (
                      <dl className="mt-2 grid gap-2 sm:grid-cols-2">
                        <div className="rounded-[var(--radius-sm)] bg-surface-2 p-2">
                          <dt className="label-caption text-ink-2">Expected</dt>
                          <dd className="mt-0.5 break-words text-caption text-ink">
                            {testCase.expected}
                          </dd>
                        </div>
                        <div className="rounded-[var(--radius-sm)] bg-danger-soft p-2">
                          <dt className="label-caption text-danger">Actual</dt>
                          <dd className="mt-0.5 break-words text-caption text-ink">
                            {testCase.actual}
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
