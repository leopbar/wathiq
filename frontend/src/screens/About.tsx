import { useQuery } from "@tanstack/react-query";
import { Cloud, FlaskConical, GitBranch, Layers, Workflow } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { qk } from "@/lib/query";
import type { SystemGraph, SystemInfo } from "@/lib/types";
import { formatDateTime, formatRelative } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { ErrorState } from "@/components/ErrorState";
import { EmptyState } from "@/components/EmptyState";
import { DetailSkeleton, ListSkeleton } from "@/components/Skeletons";
import { MermaidDiagram } from "@/components/MermaidDiagram";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs } from "@/components/ui/tabs";
import { Skeleton } from "@/components/ui/skeleton";
import { StackTable } from "./about/StackTable";
import { ServiceList } from "./about/ServiceList";

const PITCH = [
  {
    icon: Workflow,
    title: "Two layers, one identifier",
    body: "Orkes Conductor runs the business process; LangGraph runs the AI reasoning inside one agent task. The Conductor workflow id is the LangGraph thread id, so a single identifier ties the process, the agent run and the audit trail together.",
  },
  {
    icon: Layers,
    title: "Assurance before automation",
    body: "Every extracted value carries a calibrated confidence and a source region. Cases pass straight through only when the evidence supports it; everything else interrupts for a human at a mandatory or dynamic review point.",
  },
  {
    icon: GitBranch,
    title: "Configuration, not code",
    body: "A new document type is a schema, a prompt version, cross-field rules and a golden set. Demo and Azure modes run the same code paths behind a provider interface.",
  },
];

export default function About() {
  const info = useQuery({
    queryKey: qk.systemInfo,
    queryFn: () => apiFetch<SystemInfo>("/system/info"),
  });

  const graph = useQuery({
    queryKey: qk.systemGraph,
    queryFn: () => apiFetch<SystemGraph>("/system/graph"),
  });

  if (info.isPending) return <DetailSkeleton />;
  if (info.isError) {
    return (
      <Card>
        <ErrorState
          error={info.error}
          onRetry={() => void info.refetch()}
          title="System information could not be loaded"
        />
      </Card>
    );
  }

  const demo = info.data.mode === "demo";

  const diagramTabs = [
    ...info.data.diagrams.map((diagram) => ({
      value: diagram.key,
      label: diagram.title,
      content: (
        <div className="p-4">
          <MermaidDiagram chart={diagram.mermaid} ariaLabel={diagram.title} />
        </div>
      ),
    })),
    {
      value: "langgraph",
      label: "Live agent graph",
      content: (
        <div className="p-4">
          {graph.isPending ? (
            <Skeleton className="h-64 w-full" />
          ) : graph.isError ? (
            <ErrorState
              error={graph.error}
              onRetry={() => void graph.refetch()}
              title="The graph could not be fetched"
            />
          ) : (
            <>
              <MermaidDiagram
                chart={graph.data.mermaid}
                ariaLabel="LangGraph agent graph"
              />
              <p className="mt-3 text-caption text-ink-2">
                Rendered from the graph's own <code>draw_mermaid()</code> output, so this picture
                cannot drift from the code that runs.
              </p>
            </>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-5">
      <PageHeader
        title="About the system"
        description="What Wathiq does, how the parts fit together, and why each piece was chosen over its alternative."
        actions={
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge tone={demo ? "warning" : "info"}>
              {demo ? (
                <FlaskConical className="h-3 w-3" aria-hidden />
              ) : (
                <Cloud className="h-3 w-3" aria-hidden />
              )}
              {info.data.mode.toUpperCase()}
            </Badge>
            <Badge tone="outline">v{info.data.version}</Badge>
            <Badge tone="outline">
              <code dir="ltr">{info.data.build_sha.slice(0, 8)}</code>
            </Badge>
          </div>
        }
      />

      <div className="grid gap-3 lg:grid-cols-3">
        {PITCH.map((item) => (
          <Card key={item.title} className="p-5">
            <span className="flex h-9 w-9 items-center justify-center rounded-[var(--radius)] bg-primary-soft text-primary">
              <item.icon className="h-4 w-4" aria-hidden />
            </span>
            <p className="mt-3 text-body font-semibold text-ink">{item.title}</p>
            <p className="mt-1.5 text-small leading-5 text-ink-2">{item.body}</p>
          </Card>
        ))}
      </div>

      <Card className="overflow-hidden">
        <CardHeader
          title="Architecture"
          description="The same diagrams the backend ships, rendered live from Mermaid source."
        />
        {diagramTabs.length === 0 ? (
          <EmptyState title="No diagrams published" />
        ) : (
          <Tabs items={diagramTabs} listClassName="px-3" />
        )}
      </Card>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
        <div className="space-y-4">
          <h2 className="text-h2 font-semibold text-ink">Stack and reasoning</h2>
          {info.data.stack.length === 0 ? (
            <Card>
              <EmptyState title="No stack recorded" />
            </Card>
          ) : (
            <StackTable stack={info.data.stack} />
          )}
        </div>

        <div className="space-y-4">
          <Card className="overflow-hidden">
            <CardHeader
              title="Service status"
              description="Live health of each dependency in this deployment."
            />
            {info.data.services.length === 0 ? (
              <ListSkeleton rows={3} />
            ) : (
              <ServiceList services={info.data.services} />
            )}
          </Card>

          <Card className="p-5">
            <h3 className="text-h2 font-semibold text-ink">Run mode</h3>
            <p className="mt-1.5 text-small leading-5 text-ink-2">
              {demo
                ? "Demo mode: a deterministic fake model, demo OCR, a simulated core banking system and synthetic data. The demo runs fully offline, so it cannot fail because of a network or a quota."
                : "Azure mode: Azure AI Foundry, Document Intelligence, Content Safety and AI Search are live. Only the providers behind the interfaces change — the application code is identical."}
            </p>
            <dl className="mt-4 space-y-2">
              <div className="flex justify-between gap-3">
                <dt className="text-caption text-ink-2">Build</dt>
                <dd className="text-caption text-ink tabular" dir="ltr">
                  {info.data.build_sha}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-caption text-ink-2">Started</dt>
                <dd className="text-caption text-ink">
                  {formatDateTime(info.data.started_at)}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-caption text-ink-2">Last restart</dt>
                <dd className="text-caption text-ink">{formatRelative(info.data.started_at)}</dd>
              </div>
            </dl>
          </Card>
        </div>
      </div>
    </div>
  );
}
