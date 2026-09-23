import { useQuery } from "@tanstack/react-query";
import { Trans, useTranslation } from "react-i18next";
import { ExternalLink, Plug } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { qk } from "@/lib/query";
import type { Integration } from "@/lib/types";
import { titleCase } from "@/lib/format";
import { Card } from "@/components/ui/card";
import { SimulatedBadge } from "@/components/SimulatedBadge";
import { ListSkeleton } from "@/components/Skeletons";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";

export function IntegrationsTab() {
  const { t } = useTranslation();
  const query = useQuery({
    queryKey: qk.integrations,
    queryFn: () => apiFetch<Integration[]>("/settings/integrations"),
  });

  if (query.isPending) return <ListSkeleton rows={6} />;
  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }
  if (query.data.length === 0) {
    return <EmptyState icon={Plug} title={t("settings.integrations.empty")} />;
  }

  const groups = query.data.reduce<Record<string, Integration[]>>((acc, integration) => {
    (acc[integration.category] ??= []).push(integration);
    return acc;
  }, {});

  return (
    <div className="space-y-5 pt-4">
      <p className="text-small text-ink-2">
        <Trans
          i18nKey="settings.integrations.intro"
          components={{ b: <span className="font-medium text-ink" /> }}
        />
      </p>

      {Object.entries(groups).map(([category, integrations]) => (
        <section key={category}>
          <h3 className="label-caption mb-2 text-ink-2">
            {t(`settings.integrations.category.${category}`, {
              defaultValue: titleCase(category),
            })}
          </h3>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {integrations.map((integration) => (
              <Card key={integration.key} className="flex flex-col p-4">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-small font-semibold text-ink">{integration.name}</p>
                  <SimulatedBadge status={integration.status} />
                </div>
                <p className="mt-1.5 flex-1 text-caption leading-4 text-ink-2">
                  {integration.detail}
                </p>
                <div className="mt-3 flex items-center justify-between gap-2">
                  <code className="truncate text-caption text-ink-2/80" dir="ltr">
                    {integration.key}
                  </code>
                  {integration.docs_url ? (
                    <a
                      href={integration.docs_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-caption text-primary hover:underline"
                    >
                      {t("settings.integrations.docs")}
                      <ExternalLink className="h-3 w-3 rtl:-scale-x-100" aria-hidden />
                    </a>
                  ) : null}
                </div>
              </Card>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
