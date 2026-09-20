import { useQuery } from "@tanstack/react-query";
import { Cloud, FlaskConical } from "lucide-react";
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
  const { data, isPending, isError } = useMode();

  if (isPending) return <Skeleton className="h-5 w-16 rounded-full" />;
  if (isError || !data) {
    return (
      <Tooltip content="The API did not answer the mode probe.">
        <span className="inline-flex">
          <Badge tone="outline">MODE ?</Badge>
        </span>
      </Tooltip>
    );
  }

  const demo = data.mode === "demo";
  return (
    <Tooltip
      content={
        demo
          ? `Demo mode · v${data.version} — fake model, local services, synthetic data. Nothing leaves this machine.`
          : `Azure mode · v${data.version} — real Azure AI services are in use.`
      }
    >
      <span className="inline-flex">
        <Badge tone={demo ? "warning" : "info"} className="font-semibold tracking-wide">
          {demo ? (
            <FlaskConical className="h-3 w-3" aria-hidden />
          ) : (
            <Cloud className="h-3 w-3" aria-hidden />
          )}
          {data.mode.toUpperCase()}
        </Badge>
      </span>
    </Tooltip>
  );
}
