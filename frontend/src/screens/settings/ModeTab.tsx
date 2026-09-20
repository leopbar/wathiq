import { Check, Cloud, FlaskConical, X } from "lucide-react";
import { useMode } from "@/components/ModeBadge";
import { titleCase } from "@/lib/format";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ListSkeleton } from "@/components/Skeletons";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";

export function ModeTab() {
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
              {demo ? "Demo mode" : "Azure mode"}
              <Badge tone="outline" className="ms-2 align-middle">
                v{query.data.version}
              </Badge>
            </p>
            <p className="mt-1.5 text-small leading-5 text-ink-2">
              {demo
                ? "Everything runs locally: a deterministic fake model, demo OCR, a simulated core banking system and synthetic data. Nothing is sent to an external service, so the demo cannot break because of a network or quota problem."
                : "Azure AI Foundry, Document Intelligence, Content Safety and AI Search are in use with the keys from the environment. The same code paths run in both modes — only the provider behind the interface changes."}
            </p>
            <p className="mt-2 text-caption text-ink-2">
              The mode is configuration only. Switching it does not change a line of application
              code.
            </p>
          </div>
        </div>
      </Card>

      <Card className="overflow-hidden">
        <CardHeader title="Feature flags" description="What this build has switched on." />
        {features.length === 0 ? (
          <EmptyState title="No flags reported" />
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
                <span className="flex-1 text-small text-ink">{titleCase(key)}</span>
                <Badge tone={enabled ? "success" : "neutral"}>{enabled ? "on" : "off"}</Badge>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
