import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Lock, PenLine, ShieldCheck } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { qk } from "@/lib/query";
import { formatPercent } from "@/lib/format";
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
  const { t } = useTranslation();
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-small font-semibold text-ink">{server.name}</p>
        {server.can_write ? (
          <Tooltip content={t("settings.assurance.canWriteHint")}>
            <span className="inline-flex">
              <Badge tone="warning">
                <PenLine className="h-3 w-3" aria-hidden />
                {t("settings.assurance.canWrite")}
              </Badge>
            </span>
          </Tooltip>
        ) : (
          <Tooltip content={t("settings.assurance.readOnlyHint")}>
            <span className="inline-flex">
              <Badge tone="success">
                <Lock className="h-3 w-3" aria-hidden />
                {t("settings.assurance.readOnly")}
              </Badge>
            </span>
          </Tooltip>
        )}
      </div>

      <dl className="mt-3 space-y-2">
        <div>
          <dt className="label-caption text-ink-2">{t("settings.assurance.tools")}</dt>
          <dd className="mt-0.5 flex flex-wrap gap-1">
            {server.tools.map((tool) => (
              <code key={tool} className="text-caption text-ink-2" dir="ltr">
                {tool}
              </code>
            ))}
          </dd>
        </div>
        <div>
          <dt className="label-caption text-ink-2">{t("settings.assurance.allowedNodes")}</dt>
          <dd className="mt-0.5 flex flex-wrap gap-1">
            {server.used_by_nodes.map((node) => (
              <Badge key={node} tone="outline">
                <bdi>{node}</bdi>
              </Badge>
            ))}
          </dd>
        </div>
        <div>
          <dt className="label-caption text-ink-2">{t("settings.assurance.addressConfigured")}</dt>
          <dd className="mt-0.5">
            <Badge tone={server.url_configured ? "success" : "warning"}>
              {server.url_configured
                ? t("settings.assurance.yes")
                : t("settings.assurance.notConfigured")}
            </Badge>
          </dd>
        </div>
      </dl>
    </Card>
  );
}

function RulePackCard({ pack }: { pack: RulePack }) {
  const { t } = useTranslation();
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
        action={
          <Badge tone="neutral">
            {t("settings.assurance.rules", { count: pack.rules.length })}
          </Badge>
        }
      />
      <ul className="divide-y divide-border">
        {pack.rules.map((rule) => (
          <li key={rule.id} className="px-5 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <code className="text-caption text-ink" dir="ltr">
                {rule.id}
              </code>
              <Badge tone={SEVERITY_TONE[rule.severity]}>
                {t(`settings.assurance.severity.${rule.severity}`)}
              </Badge>
              {rule.policy ? (
                <Badge tone="outline">
                  <bdi>{rule.policy}</bdi>
                </Badge>
              ) : null}
              {rule.check ? (
                <Tooltip content={t("settings.assurance.namedCheckHint")}>
                  <span className="inline-flex">
                    <Badge tone="info">{t("settings.assurance.namedCheck")}</Badge>
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
  const { t } = useTranslation();
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
      <p className="text-small text-ink-2">{t("settings.assurance.intro")}</p>

      <section>
        <h3 className="label-caption mb-2 text-ink-2">
          {t("settings.assurance.guardrailsHeading")}
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
                  <dt className="label-caption text-ink-2">{t("settings.assurance.now")}</dt>
                  <dd className="text-caption text-ink">{guardrail.implementation}</dd>
                </div>
                <div>
                  <dt className="label-caption text-ink-2">
                    {t("settings.assurance.inAzureMode")}
                  </dt>
                  <dd className="text-caption text-ink-2">{guardrail.azure}</dd>
                </div>
              </dl>
            </Card>
          ))}
        </div>
      </section>

      <section>
        <h3 className="label-caption mb-2 text-ink-2">
          {t("settings.assurance.confidenceHeading")}
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
                  {formatPercent(signal.weight)}
                </span>
              </li>
            ))}
          </ul>
          <p className="mt-3 border-t border-border pt-3 text-caption text-ink-2">
            {t("settings.assurance.calibrationLead")}{" "}
            {info.calibration.fitted
              ? t("settings.assurance.calibrationFitted", {
                  count: info.calibration.sample_count,
                })
              : t("settings.assurance.calibrationNotFitted")}{" "}
            {t("settings.assurance.calibrationTail")}
          </p>
        </Card>
      </section>

      <section>
        <h3 className="label-caption mb-2 text-ink-2">
          {t("settings.assurance.toolServersHeading")}
        </h3>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {info.tool_servers.map((server) => (
            <ToolServerCard key={server.key} server={server} />
          ))}
        </div>
        <p className="mt-2 text-caption text-ink-2">{t("settings.assurance.toolServersNote")}</p>
      </section>

      <section>
        <h3 className="label-caption mb-2 text-ink-2">
          {t("settings.assurance.rulePacksHeading")}
        </h3>
        <div className="space-y-3">
          {info.rule_packs.map((pack) => (
            <RulePackCard key={pack.id} pack={pack} />
          ))}
        </div>
        <p className="mt-2 text-caption text-ink-2">
          {t("settings.assurance.namedChecksNote", {
            checks: info.registered_checks.join(", "),
          })}
        </p>
      </section>

      <section>
        <h3 className="label-caption mb-2 text-ink-2">{t("settings.assurance.policyHeading")}</h3>
        <Card className="p-4">
          <ul className="space-y-1">
            {info.policy_documents.map((document) => (
              <li key={document.name} className="flex items-center justify-between gap-3">
                <span className="text-small text-ink">{document.name}</span>
                <Badge tone="outline">
                  {t("settings.assurance.sections", { count: document.sections })}
                </Badge>
              </li>
            ))}
          </ul>
          <p className="mt-3 border-t border-border pt-3 text-caption text-ink-2">
            {t("settings.assurance.policyNote", { embedder: info.embedder })}
          </p>
        </Card>
      </section>
    </div>
  );
}
