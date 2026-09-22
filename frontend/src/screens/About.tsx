import { useQuery } from "@tanstack/react-query";
import { Trans, useTranslation } from "react-i18next";
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
  { key: "twoLayers", icon: Workflow },
  { key: "assurance", icon: Layers },
  { key: "configuration", icon: GitBranch },
] as const;

export default function About() {
  const { t } = useTranslation();
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
          title={t("about.loadError")}
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
        <div className="p-4" dir="ltr">
          <MermaidDiagram chart={diagram.mermaid} ariaLabel={diagram.title} />
        </div>
      ),
    })),
    {
      value: "langgraph",
      label: t("about.liveGraph"),
      content: (
        <div className="p-4">
          {graph.isPending ? (
            <Skeleton className="h-64 w-full" />
          ) : graph.isError ? (
            <ErrorState
              error={graph.error}
              onRetry={() => void graph.refetch()}
              title={t("about.graphError")}
            />
          ) : (
            <>
              <div dir="ltr">
                <MermaidDiagram chart={graph.data.mermaid} ariaLabel={t("about.graphAria")} />
              </div>
              <p className="mt-3 text-caption text-ink-2">
                <Trans
                  i18nKey="about.graphNote"
                  components={{ code: <code dir="ltr" /> }}
                />
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
        title={t("nav.about")}
        description={t("about.description")}
        actions={
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge tone={demo ? "warning" : "info"}>
              {demo ? (
                <FlaskConical className="h-3 w-3" aria-hidden />
              ) : (
                <Cloud className="h-3 w-3" aria-hidden />
              )}
              {t(`mode.badge.${info.data.mode}`, { defaultValue: info.data.mode.toUpperCase() })}
            </Badge>
            <Badge tone="outline">
              <bdi>v{info.data.version}</bdi>
            </Badge>
            <Badge tone="outline">
              <code dir="ltr">{info.data.build_sha.slice(0, 8)}</code>
            </Badge>
          </div>
        }
      />

      <div className="grid gap-3 lg:grid-cols-3">
        {PITCH.map((item) => (
          <Card key={item.key} className="p-5">
            <span className="flex h-9 w-9 items-center justify-center rounded-[var(--radius)] bg-primary-soft text-primary">
              <item.icon className="h-4 w-4" aria-hidden />
            </span>
            <p className="mt-3 text-body font-semibold text-ink">
              {t(`about.pitch.${item.key}.title`)}
            </p>
            <p className="mt-1.5 text-small leading-5 text-ink-2">
              {t(`about.pitch.${item.key}.body`)}
            </p>
          </Card>
        ))}
      </div>

      <Card className="overflow-hidden">
        <CardHeader
          title={t("about.architecture")}
          description={t("about.architectureDescription")}
        />
        {diagramTabs.length === 0 ? (
          <EmptyState title={t("about.noDiagrams")} />
        ) : (
          <Tabs items={diagramTabs} listClassName="px-3" />
        )}
      </Card>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]">
        <div className="space-y-4">
          <h2 className="text-h2 font-semibold text-ink">{t("about.stackHeading")}</h2>
          {info.data.stack.length === 0 ? (
            <Card>
              <EmptyState title={t("about.noStack")} />
            </Card>
          ) : (
            <StackTable stack={info.data.stack} />
          )}
        </div>

        <div className="space-y-4">
          <Card className="overflow-hidden">
            <CardHeader
              title={t("about.serviceStatus")}
              description={t("about.serviceStatusDescription")}
            />
            {info.data.services.length === 0 ? (
              <ListSkeleton rows={3} />
            ) : (
              <ServiceList services={info.data.services} />
            )}
          </Card>

          <Card className="p-5">
            <h3 className="text-h2 font-semibold text-ink">{t("about.runMode")}</h3>
            <p className="mt-1.5 text-small leading-5 text-ink-2">
              {demo ? t("about.demoBody") : t("about.azureBody")}
            </p>
            <dl className="mt-4 space-y-2">
              <div className="flex justify-between gap-3">
                <dt className="text-caption text-ink-2">{t("about.build")}</dt>
                <dd className="text-caption text-ink tabular" dir="ltr">
                  {info.data.build_sha}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-caption text-ink-2">{t("about.started")}</dt>
                <dd className="text-caption text-ink">
                  {formatDateTime(info.data.started_at)}
                </dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-caption text-ink-2">{t("about.lastRestart")}</dt>
                <dd className="text-caption text-ink">{formatRelative(info.data.started_at)}</dd>
              </div>
            </dl>
          </Card>
        </div>
      </div>
    </div>
  );
}
