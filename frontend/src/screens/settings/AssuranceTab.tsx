import { useQuery } from "@tanstack/react-query";
import { Lock, PenLine, ShieldCheck } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { qk } from "@/lib/query";
import type { AssuranceInfo, RulePack, Severity, ToolServer } from "@/lib/types";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ListSkeleton } from "@/components/Skeletons";
import { ErrorState } from "@/components/ErrorState";
import { Tooltip } from "@/components/ui/tooltip";

/**
 * How the agent assures its own answers.
 *
 * Every number and every name on this page is read from the running code — the guardrail
 * list, the signal weights, the tool allowlist, the rule packs on disk. Nothing here is a
 * hand-written description that can quietly stop being true.
 */

const SEVERITY_TONE: Record<Severity, "danger" | "warning" | "info"> = {
  critical: "danger",
  warning: "warning",
  info: "info",
};

function ToolServerCard({ server }: { server: ToolServer }) {
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-small font-semibold text-ink">{server.name}</p>
        {server.can_write ? (
          <Tooltip content="This server can change a system of record. Only the posting step may call it, and only after a human approved.">
            <span className="inline-flex">
              <Badge tone="warning">
                <PenLine className="h-3 w-3" aria-hidden />
                can write
              </Badge>
            </span>
          </Tooltip>
        ) : (
          <Tooltip content="Read-only: this server exposes no tool that changes anything.">
            <span className="inline-flex">
              <Badge tone="success">
                <Lock className="h-3 w-3" aria-hidden />
                read only
              </Badge>
            </span>
          </Tooltip>
        )}
      </div>

      <dl className="mt-3 space-y-2">
        <div>
          <dt className="label-caption text-ink-2">Tools</dt>
          <dd className="mt-0.5 flex flex-wrap gap-1">
            {server.tools.map((tool) => (
              <code key={tool} className="text-caption text-ink-2" dir="ltr">
                {tool}
              </code>
            ))}
          </dd>
        </div>
        <div>
          <dt className="label-caption text-ink-2">Graph nodes allowed to call it</dt>
          <dd className="mt-0.5 flex flex-wrap gap-1">
            {server.used_by_nodes.map((node) => (
              <Badge key={node} tone="outline">
                {node}
              </Badge>
            ))}
          </dd>
        </div>
        <div>
          <dt className="label-caption text-ink-2">Address configured</dt>
          <dd className="mt-0.5">
            <Badge tone={server.url_configured ? "success" : "warning"}>
              {server.url_configured ? "yes" : "not configured"}
            </Badge>
          </dd>
        </div>
      </dl>
    </Card>
  );
}

function RulePackCard({ pack }: { pack: RulePack }) {
  return (
    <Card>
      <CardHeader
        title={
          <span className="flex flex-wrap items-center gap-2">
            {pack.title}
            <code className="text-caption text-ink-2" dir="ltr">
              {pack.id}@{pack.version}
            </code>
          </span>
        }
        description={pack.description}
        action={<Badge tone="neutral">{pack.rules.length} rules</Badge>}
      />
      <ul className="divide-y divide-border">
        {pack.rules.map((rule) => (
          <li key={rule.id} className="px-5 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <code className="text-caption text-ink" dir="ltr">
                {rule.id}
              </code>
              <Badge tone={SEVERITY_TONE[rule.severity]}>{rule.severity}</Badge>
              {rule.policy ? <Badge tone="outline">{rule.policy}</Badge> : null}
              {rule.check ? (
                <Tooltip content="A named check written in Python. A rule pack refers to it by name; adding a new kind of check is code, adding a rule is configuration.">
                  <span className="inline-flex">
                    <Badge tone="info">named check</Badge>
                  </span>
                </Tooltip>
              ) : null}
            </div>
            <p className="mt-1 text-small text-ink">{rule.message}</p>
            <code className="mt-1 block text-caption text-ink-2" dir="ltr">
              {rule.expr ?? `check: ${rule.check}`}
            </code>
            {rule.explain ? (
              <p className="mt-1 text-caption text-ink-2">{rule.explain}</p>
            ) : null}
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function AssuranceTab() {
  const query = useQuery({
    queryKey: qk.assurance,
    queryFn: () => apiFetch<AssuranceInfo>("/settings/assurance"),
  });

  if (query.isPending) return <ListSkeleton rows={6} />;
  if (query.isError) {
    return <ErrorState error={query.error} onRetry={() => void query.refetch()} />;
  }

  const info = query.data;

  return (
    <div className="space-y-6 pt-4">
      <p className="text-small text-ink-2">
        Everything on this page is read from the code that runs: the guardrails that are
        installed, the weights the confidence is built from, the tools each part of the agent is
        allowed to call, and the rule files on disk. It cannot describe a system we are not
        running.
      </p>

      <section>
        <h3 className="label-caption mb-2 text-ink-2">
          Guardrails · run on every document before anything reads it
        </h3>
        <div className="grid gap-3 md:grid-cols-2">
          {info.guardrails.map((guardrail) => (
            <Card key={guardrail.key} className="p-4">
              <p className="flex items-center gap-1.5 text-small font-semibold text-ink">
                <ShieldCheck className="h-3.5 w-3.5 text-primary" aria-hidden />
                {guardrail.name}
              </p>
              <p className="mt-1 text-caption text-ink-2">{guardrail.purpose}</p>
              <dl className="mt-2 space-y-1">
                <div>
                  <dt className="label-caption text-ink-2">Now</dt>
                  <dd className="text-caption text-ink">{guardrail.implementation}</dd>
                </div>
                <div>
                  <dt className="label-caption text-ink-2">In Azure mode</dt>
                  <dd className="text-caption text-ink-2">{guardrail.azure}</dd>
                </div>
              </dl>
            </Card>
          ))}
        </div>
      </section>

      <section>
        <h3 className="label-caption mb-2 text-ink-2">
          Confidence · every field&rsquo;s score is built from these five signals
        </h3>
        <Card className="p-4">
          <ul className="space-y-2">
            {info.confidence_signals.map((signal) => (
              <li key={signal.key} className="flex items-center gap-3">
                <span className="w-44 shrink-0 text-small text-ink">{signal.label}</span>
                <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
                  <span
                    className="block h-full rounded-full bg-primary"
                    style={{ width: `${Math.round(signal.weight * 100)}%` }}
                  />
                </span>
                <span className="w-12 text-end text-caption tabular text-ink-2">
                  {Math.round(signal.weight * 100)}%
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-3 border-t border-border pt-3 text-caption text-ink-2">
            The weighted total is the raw score. It is then mapped through the calibration curve:{" "}
            {info.calibration.fitted
              ? `fitted on ${info.calibration.sample_count} reviewed field(s).`
              : "not fitted yet, so raw scores are shown as raw."}{" "}
            A signal that has not been measured yet is left out and the rest are re-weighted, so a
            field is never punished for a check that has not run.
          </p>
        </Card>
      </section>

      <section>
        <h3 className="label-caption mb-2 text-ink-2">
          MCP tool servers · least privilege, one process each
        </h3>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {info.tool_servers.map((server) => (
            <ToolServerCard key={server.key} server={server} />
          ))}
        </div>
        <p className="mt-2 text-caption text-ink-2">
          The investigator is given the registry, the screening list and the read-only document
          store. It has no address for core banking, and the broker in the API refuses the call
          even if it had one. That is two independent locks on the only server that can write.
        </p>
      </section>

      <section>
        <h3 className="label-caption mb-2 text-ink-2">
          Rule packs · versioned YAML, one file per document type
        </h3>
        <div className="space-y-3">
          {info.rule_packs.map((pack) => (
            <RulePackCard key={pack.id} pack={pack} />
          ))}
        </div>
        <p className="mt-2 text-caption text-ink-2">
          Named checks registered in code: {info.registered_checks.join(", ")}. A rule pack may
          refer to one by name; everything else is an expression, which is why adding a document
          type is a configuration change.
        </p>
      </section>

      <section>
        <h3 className="label-caption mb-2 text-ink-2">
          Policy pack · what findings cite, indexed for retrieval
        </h3>
        <Card className="p-4">
          <ul className="space-y-1">
            {info.policy_documents.map((document) => (
              <li key={document.name} className="flex items-center justify-between gap-3">
                <span className="text-small text-ink">{document.name}</span>
                <Badge tone="outline">{document.sections} sections</Badge>
              </li>
            ))}
          </ul>
          <p className="mt-3 border-t border-border pt-3 text-caption text-ink-2">
            Synthetic policies written for this demonstration — not real bank policy. Indexed
            with: {info.embedder}. A rule that names its section quotes that section directly; a
            finding with no citation gets the nearest section by vector search, or no quote at
            all rather than a misleading one.
          </p>
        </Card>
      </section>
    </div>
  );
}
