import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { apiFetch } from "@/lib/api";
import type { QualityRun } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ErrorState";
import { RunDrawer } from "../quality/RunDrawer";

export function PromptEvaluations({ promptKey, version, mayRun }: {
  promptKey: string; version: string; mayRun: boolean;
}) {
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
  return <div className="space-y-3 pt-3">
    <p className="text-small text-ink-2">Runs template checks and golden-set correctness against the demo backend, linked to this exact prompt version.</p>
    <p className="text-small text-ink-2">Wording sensitivity is not measured: the demo reader does not consume prompt instructions. No model robustness score is claimed.</p>
    <Button size="sm" disabled={!mayRun} loading={evaluate.isPending} onClick={() => evaluate.mutate()}>Evaluate this version</Button>
    {history.isError ? <ErrorState error={history.error} onRetry={() => void history.refetch()} /> : null}
    {history.data?.length === 0 ? <p className="text-small text-ink-2">No measured evaluations for this version yet.</p> : null}
    {history.data?.map(run => <button key={run.id} className="block w-full rounded-lg border border-border p-3 text-start text-small" onClick={() => setOpenRun(run.id)}>
      {run.passed} passed · {run.failed} failed · {run.passed + run.failed} checks · {new Date(run.started_at).toLocaleString()}
    </button>)}
    <RunDrawer runId={openRun} onOpenChange={open => !open && setOpenRun(null)} />
  </div>;
}
