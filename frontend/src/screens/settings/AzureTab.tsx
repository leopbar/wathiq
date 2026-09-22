import { useQuery } from "@tanstack/react-query";
import { Trans, useTranslation } from "react-i18next";
import { Cloud, KeyRound, ShieldCheck } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { qk } from "@/lib/query";
import type { AzureInfo } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { ListSkeleton } from "@/components/Skeletons";
import { ErrorState } from "@/components/ErrorState";

const EMPHASIS = { b: <span className="font-medium text-ink" /> };

/**
 * Which Azure services this deployment actually uses.
 *
 * Generated from the running configuration, like the Assurance and Process tabs — so it
 * cannot claim a service that is switched off. Each service shows what runs *instead* when it
 * is not configured, because "not connected" without that is only half the story: the demo
 * implementation is still doing the work, and a reviewer deserves to know which one produced
 * the numbers in front of them.
 */
export function AzureTab() {
  const { t } = useTranslation();
  const query = useQuery({
    queryKey: qk.azure,
    queryFn: () => apiFetch<AzureInfo>("/settings/azure"),
  });

  if (query.isPending) return <ListSkeleton rows={6} />;
  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }

  const info = query.data;
  const live = info.services.filter((service) => service.enabled).length;

  return (
    <div className="space-y-5 pt-4">
      <section
        className="flex flex-wrap items-center gap-2"
        aria-label={t("settings.azure.summaryLabel")}
      >
        <Badge tone={info.mode === "azure" ? "success" : "info"}>
          {t("settings.azure.mode", { mode: info.mode })}
        </Badge>
        <Badge tone={live > 0 ? "success" : "info"}>
          {t("settings.azure.servicesConnected", { live, total: info.services.length })}
        </Badge>
        <Badge tone={info.auth_backend === "entra" ? "success" : "info"}>
          {t("settings.azure.signIn", {
            backend:
              info.auth_backend === "entra"
                ? "Microsoft Entra ID"
                : t("settings.azure.localAccounts"),
          })}
        </Badge>
        {info.tracing_enabled ? (
          <Badge tone="success">{t("settings.azure.tracing")}</Badge>
        ) : null}
      </section>

      <p className="text-small text-ink-2">
        <Trans i18nKey="settings.azure.intro" components={EMPHASIS} />
      </p>

      <div className="grid gap-3 md:grid-cols-2">
        {info.services.map((service) => (
          <Card key={service.key} className="flex flex-col p-4">
            <div className="flex items-start justify-between gap-2">
              <p className="text-small font-semibold text-ink">{service.name}</p>
              <Badge tone={service.enabled ? "success" : "neutral"}>
                {service.enabled
                  ? t("settings.azure.connected")
                  : t("settings.azure.notConfigured")}
              </Badge>
            </div>

            <p className="mt-1.5 text-caption leading-4 text-ink-2">{service.detail}</p>

            {service.enabled ? (
              <code
                className="mt-2 truncate text-caption text-ink-2/80"
                title={service.endpoint}
                dir="ltr"
              >
                {service.endpoint}
              </code>
            ) : (
              <p className="mt-2 flex-1 text-caption leading-4 text-ink-2">
                <span className="font-medium text-ink">{t("settings.azure.runningInstead")}</span>{" "}
                {service.replaces}
              </p>
            )}
          </Card>
        ))}
      </div>

      <section aria-label={t("settings.azure.authLabel")}>
        <h3 className="label-caption mb-2 text-ink-2">{t("settings.azure.authHeading")}</h3>
        <Card className="space-y-2 p-4">
          <p className="flex items-center gap-2 text-small text-ink">
            <KeyRound className="size-4 shrink-0 text-ink-2" aria-hidden />
            <bdi>{info.credential}</bdi>
          </p>
          <p className="text-caption leading-4 text-ink-2">
            <Trans i18nKey="settings.azure.authBody" components={EMPHASIS} />
          </p>
        </Card>
      </section>

      <section aria-label={t("settings.azure.notConnectedLabel")}>
        <h3 className="label-caption mb-2 text-ink-2">{t("settings.azure.statedPlainly")}</h3>
        <Card className="space-y-2 p-4">
          <p className="flex items-start gap-2 text-caption leading-4 text-ink-2">
            <ShieldCheck className="mt-0.5 size-4 shrink-0" aria-hidden />
            <span>
              <Trans i18nKey="settings.azure.searchNote" components={EMPHASIS} />
            </span>
          </p>
          <p className="flex items-start gap-2 text-caption leading-4 text-ink-2">
            <Cloud className="mt-0.5 size-4 shrink-0" aria-hidden />
            <span>{t("settings.azure.simulatedNote")}</span>
          </p>
        </Card>
      </section>
    </div>
  );
}
