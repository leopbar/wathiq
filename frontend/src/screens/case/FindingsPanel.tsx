import { BookMarked, CheckCircle2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { Finding } from "@/lib/types";
import { formatDateTime } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { SeverityPill } from "@/components/StatusPill";
import { EmptyState } from "@/components/EmptyState";

const STATUS_TONE: Record<Finding["status"], "warning" | "success" | "neutral"> = {
  open: "warning",
  resolved: "success",
  waived: "neutral",
};

export function FindingsPanel({ findings }: { findings: Finding[] }) {
  const { t } = useTranslation();
  if (findings.length === 0) {
    return (
      <EmptyState
        icon={CheckCircle2}
        title={t("caseDetail.findings.empty")}
        description={t("caseDetail.findings.emptyDescription")}
      />
    );
  }

  const order = { critical: 0, warning: 1, info: 2 } as const;
  const sorted = [...findings].sort((a, b) => order[a.severity] - order[b.severity]);

  return (
    <ul className="divide-y divide-border">
      {sorted.map((finding) => (
        <li key={finding.id} className="px-4 py-3.5">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityPill severity={finding.severity} />
            <Badge tone={STATUS_TONE[finding.status]}>{t(`caseDetail.findings.status.${finding.status}`)}</Badge>
            <span className="ms-auto text-caption text-ink-2">
              {formatDateTime(finding.created_at)}
            </span>
          </div>

          <p className="mt-2 text-body font-medium text-ink">{finding.title}</p>
          <p className="mt-0.5 text-small text-ink-2">{finding.description}</p>
          <code className="mt-1 block text-caption text-ink-2/80" dir="ltr">
            {finding.code}
          </code>

          {finding.policy_quote || finding.policy_citation ? (
            <figure className="mt-2.5 rounded-[var(--radius)] border-s-2 border-primary bg-primary-soft/40 px-3 py-2">
              {finding.policy_quote ? (
                <blockquote className="text-small italic text-ink">
                  “{finding.policy_quote}”
                </blockquote>
              ) : null}
              {finding.policy_citation ? (
                <figcaption className="mt-1 flex items-center gap-1.5 text-caption text-ink-2">
                  <BookMarked className="h-3 w-3" aria-hidden />
                  <bdi>{finding.policy_citation}</bdi>
                </figcaption>
              ) : null}
            </figure>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
