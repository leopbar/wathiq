import { useQuery } from "@tanstack/react-query";
import { Cloud, FlaskConical } from "lucide-react";
import { useTranslation } from "react-i18next";
import { apiFetch } from "@/lib/api";
import type { ModeInfo } from "@/lib/types";
import { qk } from "@/lib/query";
import { Badge } from "./ui/badge";
import { Tooltip } from "./ui/tooltip";
import { Skeleton } from "./ui/skeleton";

export function useMode() {
  return useQuery({
    queryKey: qk.mode,
    queryFn: () => apiFetch<ModeInfo>("/settings/mode"),
    staleTime: 5 * 60_000,
    retry: 1,
  });
}

export function ModeBadge() {
  const { t } = useTranslation();
  const { data, isPending, isError } = useMode();

  if (isPending) return <Skeleton className="h-5 w-16 rounded-full" />;
  if (isError || !data) {
    return (
      <Tooltip content={t("mode.probeFailed")}>
        <span className="inline-flex">
          <Badge tone="outline">{t("mode.unknown")}</Badge>
        </span>
      </Tooltip>
    );
  }

  const demo = data.mode === "demo";
  return (
    <Tooltip
      content={
        demo
          ? t("mode.demoHint", { version: data.version })
          : t("mode.azureHint", { version: data.version })
      }
    >
      <span className="inline-flex">
        <Badge tone={demo ? "warning" : "info"} className="font-semibold tracking-wide">
          {demo ? (
            <FlaskConical className="h-3 w-3" aria-hidden />
          ) : (
            <Cloud className="h-3 w-3" aria-hidden />
          )}
          {t(`mode.badge.${data.mode}`, { defaultValue: data.mode.toUpperCase() })}
        </Badge>
      </span>
    </Tooltip>
  );
}
