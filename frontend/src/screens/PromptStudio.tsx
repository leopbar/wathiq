import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Archive, BadgeCheck, GitCompare, Sparkles } from "lucide-react";
import { apiFetch, buildQuery } from "@/lib/api";
import { qk } from "@/lib/query";
import type { PromptDiff, PromptSummary, PromptVersion } from "@/lib/types";
import { formatDateTime, formatPercent } from "@/lib/format";
import { cn } from "@/lib/cn";
import { useAuth } from "@/auth/useAuth";
import { can } from "@/auth/roles";
import { describeError, ErrorState } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { ListSkeleton } from "@/components/Skeletons";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Tabs } from "@/components/ui/tabs";
import { Tooltip } from "@/components/ui/tooltip";
import { CodeBlock } from "@/components/ui/code-block";
import { VersionTimeline } from "./prompts/VersionTimeline";
import { DiffViewer } from "./prompts/DiffViewer";

export default function PromptStudio() {
  const queryClient = useQueryClient();
  const { role } = useAuth();
  const mayApprove = can(role, "prompts.approve");

  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<string | null>(null);
  const [diffFrom, setDiffFrom] = useState<string>("");

  const prompts = useQuery({
    queryKey: qk.prompts,
    queryFn: () => apiFetch<PromptSummary[]>("/prompts"),
  });

  useEffect(() => {
    if (!selectedKey && prompts.data && prompts.data.length > 0) {
      setSelectedKey(prompts.data[0].key);
    }
  }, [prompts.data, selectedKey]);

  const versions = useQuery({
    queryKey: qk.promptVersions(selectedKey ?? ""),
    queryFn: () => apiFetch<PromptVersion[]>(`/prompts/${selectedKey}/versions`),
    enabled: Boolean(selectedKey),
  });

  const sortedVersions = useMemo(() => versions.data ?? [], [versions.data]);

  useEffect(() => {
    if (sortedVersions.length === 0) return;
    const exists = sortedVersions.some((v) => v.version === selectedVersion);
    if (!exists) {
      setSelectedVersion(sortedVersions[0].version);
      setDiffFrom(sortedVersions[1]?.version ?? sortedVersions[0].version);
    }
  }, [sortedVersions, selectedVersion]);

  const current = sortedVersions.find((v) => v.version === selectedVersion) ?? null;

  const diff = useQuery({
    queryKey: qk.promptDiff(selectedKey ?? "", diffFrom, selectedVersion ?? ""),
    queryFn: () =>
      apiFetch<PromptDiff>(
        `/prompts/${selectedKey}/diff${buildQuery({ from: diffFrom, to: selectedVersion })}`,
      ),
    enabled: Boolean(selectedKey && selectedVersion && diffFrom && diffFrom !== selectedVersion),
  });

  const act = useMutation({
    mutationFn: ({ action, version }: { action: "approve" | "retire"; version: string }) =>
      apiFetch<PromptVersion>(`/prompts/${selectedKey}/versions/${version}/${action}`, {
        method: "POST",
      }),
    onSuccess: (_data, variables) => {
      toast.success(variables.action === "approve" ? "Version approved" : "Version retired", {
        description: `v${variables.version} of ${selectedKey}.`,
      });
      void queryClient.invalidateQueries({ queryKey: ["prompts"] });
    },
    onError: (error) =>
      toast.error("Action failed", { description: describeError(error).message }),
  });

  const approveButton = (
    <Button
      size="sm"
      variant="primary"
      disabled={!mayApprove || !current || current.status === "approved"}
      loading={act.isPending && act.variables?.action === "approve"}
      onClick={() => current && act.mutate({ action: "approve", version: current.version })}
    >
      <BadgeCheck className="h-3.5 w-3.5" aria-hidden />
      Approve
    </Button>
  );

  const retireButton = (
    <Button
      size="sm"
      variant="secondary"
      disabled={!mayApprove || !current || current.status === "retired"}
      loading={act.isPending && act.variables?.action === "retire"}
      onClick={() => current && act.mutate({ action: "retire", version: current.version })}
    >
      <Archive className="h-3.5 w-3.5" aria-hidden />
      Retire
    </Button>
  );

  return (
    <div className="space-y-4">
      <PageHeader
        title="Prompt Studio"
        description="Every prompt is versioned with semver: MAJOR changes the output schema, MINOR adds fields, PATCH rewords. The engine only ever loads a pinned, approved version."
        actions={
          mayApprove ? (
            <div className="flex gap-2">
              {approveButton}
              {retireButton}
            </div>
          ) : (
            <Tooltip content="Only administrators can approve or retire a prompt version.">
              <div className="flex gap-2">
                {approveButton}
                {retireButton}
              </div>
            </Tooltip>
          )
        }
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,18rem)_minmax(0,1fr)]">
        <Card className="h-fit overflow-hidden">
          <CardHeader title="Prompts" />
          {prompts.isPending ? (
            <ListSkeleton rows={5} />
          ) : prompts.isError ? (
            <ErrorState error={prompts.error} onRetry={() => void prompts.refetch()} />
          ) : prompts.data.length === 0 ? (
            <EmptyState icon={Sparkles} title="No prompts registered" />
          ) : (
            <ul className="divide-y divide-border">
              {prompts.data.map((prompt) => (
                <li key={prompt.id}>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedKey(prompt.key);
                      setSelectedVersion(null);
                    }}
                    aria-current={prompt.key === selectedKey}
                    className={cn(
                      "w-full px-4 py-3 text-start transition-colors",
                      prompt.key === selectedKey ? "bg-primary-soft/60" : "hover:bg-surface-2/70",
                    )}
                  >
                    <p className="truncate text-small font-medium text-ink">{prompt.name}</p>
                    <code className="block truncate text-caption text-ink-2">{prompt.key}</code>
                    <span className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      <Badge tone="outline">v{prompt.latest_version}</Badge>
                      <Badge tone={prompt.status === "approved" ? "success" : "warning"}>
                        {prompt.status}
                      </Badge>
                      <span className="text-caption text-ink-2">
                        {prompt.versions_count} versions
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="overflow-hidden">
          {!selectedKey ? (
            <EmptyState title="Select a prompt" description="Pick a prompt to see its versions." />
          ) : versions.isPending ? (
            <ListSkeleton rows={6} />
          ) : versions.isError ? (
            <ErrorState error={versions.error} onRetry={() => void versions.refetch()} />
          ) : sortedVersions.length === 0 ? (
            <EmptyState title="No versions yet" />
          ) : (
            <div className="grid gap-0 lg:grid-cols-[minmax(0,15rem)_minmax(0,1fr)]">
              <div className="border-b border-border p-3 lg:border-b-0 lg:border-e">
                <p className="label-caption mb-2 px-1 text-ink-2">Version history</p>
                <VersionTimeline
                  versions={sortedVersions}
                  selected={selectedVersion}
                  onSelect={setSelectedVersion}
                />
              </div>

              <div className="min-w-0 p-4">
                {current ? (
                  <>
                    <div className="mb-3 flex flex-wrap items-center gap-2">
                      <h2 className="text-h2 font-semibold text-ink tabular">
                        v{current.version}
                      </h2>
                      <Badge tone={current.status === "approved" ? "success" : "warning"}>
                        {current.status}
                      </Badge>
                      {current.eval_score !== null ? (
                        <Badge tone="outline">
                          linked eval {formatPercent(current.eval_score, 1)}
                        </Badge>
                      ) : null}
                      {current.approved_by ? (
                        <span className="text-caption text-ink-2">
                          approved by {current.approved_by} ·{" "}
                          {formatDateTime(current.approved_at)}
                        </span>
                      ) : null}
                    </div>

                    {current.notes ? (
                      <p className="mb-3 rounded-[var(--radius)] border border-border bg-surface-2/60 px-3 py-2 text-small text-ink-2">
                        {current.notes}
                      </p>
                    ) : null}

                    <Tabs
                      items={[
                        {
                          value: "body",
                          label: "Prompt body",
                          content: (
                            <div className="pt-3">
                              <CodeBlock code={current.body} title={`${selectedKey}@${current.version}`} />
                            </div>
                          ),
                        },
                        {
                          value: "diff",
                          label: "Diff",
                          content: (
                            <div className="space-y-3 pt-3">
                              <div className="flex flex-wrap items-center gap-2">
                                <GitCompare className="h-4 w-4 text-ink-2" aria-hidden />
                                <span className="text-small text-ink-2">Compare from</span>
                                <Select
                                  value={diffFrom || undefined}
                                  onValueChange={setDiffFrom}
                                  ariaLabel="Diff base version"
                                  className="w-40"
                                  options={sortedVersions
                                    .filter((v) => v.version !== current.version)
                                    .map((v) => ({ value: v.version, label: `v${v.version}` }))}
                                />
                                <span className="text-small text-ink-2">
                                  to <span className="font-medium text-ink">v{current.version}</span>
                                </span>
                              </div>

                              {!diffFrom || diffFrom === current.version ? (
                                <EmptyState
                                  title="Pick a base version"
                                  description="Choose an earlier version to see what changed."
                                />
                              ) : diff.isPending ? (
                                <ListSkeleton rows={5} />
                              ) : diff.isError ? (
                                <ErrorState error={diff.error} onRetry={() => void diff.refetch()} />
                              ) : (
                                <DiffViewer diff={diff.data.unified_diff} />
                              )}
                            </div>
                          ),
                        },
                      ]}
                    />
                  </>
                ) : null}
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
