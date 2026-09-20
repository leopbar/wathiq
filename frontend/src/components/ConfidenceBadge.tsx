import { Badge } from "./ui/badge";
import { Tooltip } from "./ui/tooltip";
import { formatPercent } from "@/lib/format";

export type ConfidenceLevel = "high" | "medium" | "low";

export function confidenceLevel(value: number): ConfidenceLevel {
  if (value >= 0.9) return "high";
  if (value >= 0.7) return "medium";
  return "low";
}

const LEVEL = {
  high: { tone: "success" as const, label: "High" },
  medium: { tone: "warning" as const, label: "Medium" },
  low: { tone: "danger" as const, label: "Low" },
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
  if (value === null || value === undefined) {
    return (
      <Badge tone="outline" title="No confidence recorded">
        n/a
      </Badge>
    );
  }
  const level = confidenceLevel(value);
  const { tone, label } = LEVEL[level];

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
          Calibrated {formatPercent(value, 1)} · raw model score {formatPercent(raw, 1)}
        </span>
      }
    >
      <span className="inline-flex">{badge}</span>
    </Tooltip>
  );
}
