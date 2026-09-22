import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { apiFetch } from "@/lib/api";
import { formatDateTime, formatNumber } from "@/lib/format";
import type { QualityRun } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ErrorState";
import { RunDrawer } from "../quality/RunDrawer";

export function PromptEvaluations({
  promptKey,
  version,
  mayRun,
}: {
  promptKey: string;
  version: string;
  mayRun: boolean;
}) {
  const { t } = useTranslation();
  const client = useQueryClient();
  const [openRun, setOpenRun] = useState<string | null>(null);
  const path = `/prompts/${promptKey}/versions/${version}`;
  const history = useQuery({
    queryKey: ["prompts", promptKey, version, "evaluations"],
    queryFn: () => apiFetch<QualityRun[]>(`${path}/evaluations`),
  });
  const evaluate = useMutation({
    mutationFn: () => apiFetch<{ runs: QualityRun[] }>(`${path}/evaluate`, { method: "POST" }),
    onSuccess: ({ runs }) => {
      setOpenRun(runs[0].id);
      void client.invalidateQueries({ queryKey: ["prompts"] });
      void client.invalidateQueries({ queryKey: ["quality"] });
    },
    onError: (error) => toast.error(error.message),
  });
  return (
    <div className="space-y-3 pt-3">
      <p className="text-small text-ink-2">{t("prompts.evaluations.intro")}</p>
      <p className="text-small text-ink-2">{t("prompts.evaluations.sensitivity")}</p>
      <Button
        size="sm"
        disabled={!mayRun}
        loading={evaluate.isPending}
        onClick={() => evaluate.mutate()}
      >
        {t("prompts.evaluations.evaluate")}
      </Button>
      {history.isError ? (
        <ErrorState error={history.error} onRetry={() => void history.refetch()} />
      ) : null}
      {history.data?.length === 0 ? (
        <p className="text-small text-ink-2">{t("prompts.evaluations.empty")}</p>
      ) : null}
      {history.data?.map((run) => (
        <button
          key={run.id}
          type="button"
          className="block w-full rounded-lg border border-border p-3 text-start text-small"
          onClick={() => setOpenRun(run.id)}
        >
          {t("prompts.evaluations.summary", {
            passed: formatNumber(run.passed),
            failed: formatNumber(run.failed),
            checks: formatNumber(run.passed + run.failed),
            date: formatDateTime(run.started_at),
          })}
        </button>
      ))}
      <RunDrawer runId={openRun} onOpenChange={(open) => !open && setOpenRun(null)} />
    </div>
  );
}
