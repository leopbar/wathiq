import { CheckCircle2, CircleDot, Archive } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { PromptStatus, PromptVersion } from "@/lib/types";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/cn";
import { Badge } from "@/components/ui/badge";

const STATUS_TONE: Record<PromptStatus, "success" | "warning" | "neutral"> = {
  approved: "success",
  draft: "warning",
  retired: "neutral",
};

const STATUS_ICON: Record<PromptStatus, typeof CheckCircle2> = {
  approved: CheckCircle2,
  draft: CircleDot,
  retired: Archive,
};

export function VersionTimeline({
  versions,
  selected,
  onSelect,
}: {
  versions: PromptVersion[];
  selected: string | null;
  onSelect: (version: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <ol className="space-y-1">
      {versions.map((version) => {
        const Icon = STATUS_ICON[version.status];
        const active = version.version === selected;
        return (
          <li key={version.id}>
            <button
              type="button"
              onClick={() => onSelect(version.version)}
              aria-current={active}
              className={cn(
                "flex w-full items-start gap-2.5 rounded-[var(--radius)] px-2.5 py-2 text-start transition-colors",
                active ? "bg-primary-soft" : "hover:bg-surface-2",
              )}
            >
              <Icon
                className={cn(
                  "mt-0.5 h-4 w-4 shrink-0",
                  version.status === "approved"
                    ? "text-success"
                    : version.status === "draft"
                      ? "text-warning"
                      : "text-ink-2",
                )}
                aria-hidden
              />
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-1.5">
                  <span className="text-small font-semibold text-ink tabular">
                    v{version.version}
                  </span>
                  <Badge tone={STATUS_TONE[version.status]}>
                    {t(`prompts.status.${version.status}`)}
                  </Badge>
                </span>
                <span className="mt-0.5 block truncate text-caption text-ink-2">
                  <bdi>{version.created_by}</bdi> · {formatDateTime(version.created_at)}
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
