import { useTranslation } from "react-i18next";
import { Check, Cloud, FlaskConical, X } from "lucide-react";
import { useMode } from "@/components/ModeBadge";
import { titleCase } from "@/lib/format";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ListSkeleton } from "@/components/Skeletons";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";

export function ModeTab() {
  const { t } = useTranslation();
  const query = useMode();

  if (query.isPending) return <ListSkeleton rows={4} />;
  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }

  const demo = query.data.mode === "demo";
  const features = Object.entries(query.data.features);

  return (
    <div className="grid gap-4 pt-4 lg:grid-cols-2">
      <Card className="p-5">
        <div className="flex items-start gap-3">
          <span
            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${
              demo ? "bg-warning-soft text-warning" : "bg-info-soft text-info"
            }`}
          >
            {demo ? (
              <FlaskConical className="h-5 w-5" aria-hidden />
            ) : (
              <Cloud className="h-5 w-5" aria-hidden />
            )}
          </span>
          <div>
            <p className="text-h2 font-semibold text-ink">
              {demo ? t("settings.mode.demoTitle") : t("settings.mode.azureTitle")}
              <Badge tone="outline" className="ms-2 align-middle">
                <bdi>v{query.data.version}</bdi>
              </Badge>
            </p>
            <p className="mt-1.5 text-small leading-5 text-ink-2">
              {demo ? t("settings.mode.demoBody") : t("settings.mode.azureBody")}
            </p>
            <p className="mt-2 text-caption text-ink-2">{t("settings.mode.configOnly")}</p>
          </div>
        </div>
      </Card>

      <Card className="overflow-hidden">
        <CardHeader
          title={t("settings.mode.flagsTitle")}
          description={t("settings.mode.flagsDescription")}
        />
        {features.length === 0 ? (
          <EmptyState title={t("settings.mode.noFlags")} />
        ) : (
          <ul className="divide-y divide-border">
            {features.map(([key, enabled]) => (
              <li key={key} className="flex items-center gap-3 px-5 py-2.5">
                <span
                  className={`flex h-5 w-5 items-center justify-center rounded-full ${
                    enabled ? "bg-success-soft text-success" : "bg-surface-2 text-ink-2"
                  }`}
                >
                  {enabled ? (
                    <Check className="h-3 w-3" aria-hidden />
                  ) : (
                    <X className="h-3 w-3" aria-hidden />
                  )}
                </span>
                <span className="flex-1 text-small text-ink">
                  {t(`settings.mode.flag.${key}`, { defaultValue: titleCase(key) })}
                </span>
                <Badge tone={enabled ? "success" : "neutral"}>
                  {enabled ? t("settings.mode.on") : t("settings.mode.off")}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
