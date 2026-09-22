import { useTranslation } from "react-i18next";
import { Badge } from "./ui/badge";
import { Tooltip } from "./ui/tooltip";
import { formatPercent } from "@/lib/format";

export type ConfidenceLevel = "high" | "medium" | "low";

export function confidenceLevel(value: number): ConfidenceLevel {
  if (value >= 0.9) return "high";
  if (value >= 0.7) return "medium";
  return "low";
}

const LEVEL_TONE = {
  high: "success" as const,
  medium: "warning" as const,
  low: "danger" as const,
};

/**
 * Confidence always ships the number next to the word — colour is never the
 * only signal (DESIGN.md, WCAG AA).
 */
export function ConfidenceBadge({
  value,
  raw,
  showLabel = true,
}: {
  value: number | null | undefined;
  raw?: number | null;
  showLabel?: boolean;
}) {
  const { t } = useTranslation();
  if (value === null || value === undefined) {
    return (
      <Badge tone="outline" title={t("confidence.none")}>
        {t("common.notAvailable")}
      </Badge>
    );
  }
  const level = confidenceLevel(value);
  const tone = LEVEL_TONE[level];
  const label = t(`confidence.level.${level}`);

  const badge = (
    <Badge tone={tone}>
      {showLabel ? <span>{label}</span> : null}
      <span className="tabular font-semibold">{formatPercent(value)}</span>
    </Badge>
  );

  if (raw === null || raw === undefined) return badge;

  return (
    <Tooltip
      content={
        <span>
          {t("confidence.tooltip", {
            calibrated: formatPercent(value, 1),
            raw: formatPercent(raw, 1),
          })}
        </span>
      }
    >
      <span className="inline-flex">{badge}</span>
    </Tooltip>
  );
}
