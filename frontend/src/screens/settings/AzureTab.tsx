import { useQuery } from "@tanstack/react-query";
import { Cloud, KeyRound, ShieldCheck } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { qk } from "@/lib/query";
import type { AzureInfo } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { ListSkeleton } from "@/components/Skeletons";
import { ErrorState } from "@/components/ErrorState";

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
      <section className="flex flex-wrap items-center gap-2" aria-label="Azure mode summary">
        <Badge tone={info.mode === "azure" ? "success" : "info"}>
          Mode: {info.mode}
        </Badge>
        <Badge tone={live > 0 ? "success" : "info"}>
          {live} of {info.services.length} services connected
        </Badge>
        <Badge tone={info.auth_backend === "entra" ? "success" : "info"}>
          Sign-in: {info.auth_backend === "entra" ? "Microsoft Entra ID" : "local accounts"}
        </Badge>
        {info.tracing_enabled ? <Badge tone="success">Tracing to Azure Monitor</Badge> : null}
      </section>

      <p className="text-small text-ink-2">
        Each Azure service is switched on by <span className="font-medium text-ink">its own
        endpoint</span>, not by the mode alone. A service with no endpoint is not an error: the
        demo implementation keeps running, and this screen names it. A service that is
        configured and then fails is a different thing again — it raises, rather than quietly
        falling back, so a case is never scored by something nobody chose.
      </p>

      <div className="grid gap-3 md:grid-cols-2">
        {info.services.map((service) => (
          <Card key={service.key} className="flex flex-col p-4">
            <div className="flex items-start justify-between gap-2">
              <p className="text-small font-semibold text-ink">{service.name}</p>
              <Badge tone={service.enabled ? "success" : "neutral"}>
                {service.enabled ? "Connected" : "Not configured"}
              </Badge>
            </div>

            <p className="mt-1.5 text-caption leading-4 text-ink-2">{service.detail}</p>

            {service.enabled ? (
              <code className="mt-2 truncate text-caption text-ink-2/80" title={service.endpoint}>
                {service.endpoint}
              </code>
            ) : (
              <p className="mt-2 flex-1 text-caption leading-4 text-ink-2">
                <span className="font-medium text-ink">Running instead:</span>{" "}
                {service.replaces}
              </p>
            )}
          </Card>
        ))}
      </div>

      <section aria-label="How Wathiq authenticates to Azure">
        <h3 className="label-caption mb-2 text-ink-2">Authentication</h3>
        <Card className="space-y-2 p-4">
          <p className="flex items-center gap-2 text-small text-ink">
            <KeyRound className="size-4 shrink-0 text-ink-2" aria-hidden />
            {info.credential}
          </p>
          <p className="text-caption leading-4 text-ink-2">
            On AKS this resolves to a <span className="font-medium text-ink">workload
            identity</span>: the pod exchanges its Kubernetes service-account token for an Entra
            token. No key for any Azure service is stored in the image, in a manifest or in the
            repository. The only two secrets that exist are the database password and the JWT
            signing key, and both are mounted from Key Vault.
          </p>
        </Card>
      </section>

      <section aria-label="What is not connected">
        <h3 className="label-caption mb-2 text-ink-2">Stated plainly</h3>
        <Card className="space-y-2 p-4">
          <p className="flex items-start gap-2 text-caption leading-4 text-ink-2">
            <ShieldCheck className="mt-0.5 size-4 shrink-0" aria-hidden />
            <span>
              Azure AI Search is <span className="font-medium text-ink">deliberately not
              deployed</span>. The free tier in this subscription belongs to another system, and
              a paid Basic service would replace a pgvector retriever that already returns real
              policy citations. The adapter is written and tested; it is not paid for.
            </span>
          </p>
          <p className="flex items-start gap-2 text-caption leading-4 text-ink-2">
            <Cloud className="mt-0.5 size-4 shrink-0" aria-hidden />
            <span>
              Core banking, the company registry and the sanctions list remain simulated in every
              mode. They are MCP tool servers with synthetic data, and the Integrations tab says
              so. Azure mode changes how documents are read and reasoned about — not what they
              are checked against.
            </span>
          </p>
        </Card>
      </section>
    </div>
  );
}
