import { useTranslation } from "react-i18next";
import type { ConfidenceSignal } from "@/lib/types";
import { formatPercent } from "@/lib/format";
import { cn } from "@/lib/cn";

/**
 * Why a field scored what it did.
 *
 * A reviewer cannot act on "73%". They can act on "the value is not on the page", which is
 * the signal that produced the 73%. Each bar is one signal; its width is how strong the
 * signal was, and the percentage after the label is how much that signal counts.
 */
export function ConfidenceSignals({
  signals,
  className,
}: {
  signals: ConfidenceSignal[];
  className?: string;
}) {
  const { t } = useTranslation();
  if (signals.length === 0) return null;

  return (
    <dl className={cn("space-y-1.5", className)}>
      {signals.map((signal) => {
        const strong = signal.value >= 0.75;
        const weak = signal.value < 0.4;
        return (
          <div key={signal.key}>
            <div className="flex items-baseline justify-between gap-2">
              <dt className="text-caption text-ink-2">
                {signal.label}
                <span className="text-ink-2/70">
                  {" "}
                  · {t("caseDetail.signals.weight", { weight: formatPercent(signal.weight) })}
                </span>
              </dt>
              <dd className="text-caption tabular text-ink-2">
                {formatPercent(signal.value)}
              </dd>
            </div>
            <div
              className="mt-0.5 h-1 w-full overflow-hidden rounded-full bg-surface-2"
              role="presentation"
            >
              <div
                className={cn(
                  "h-full rounded-full",
                  weak ? "bg-danger" : strong ? "bg-success" : "bg-warning",
                )}
                style={{ width: `${Math.max(2, Math.round(signal.value * 100))}%` }}
              />
            </div>
            <p className="mt-0.5 text-caption text-ink-2/80">{signal.detail}</p>
          </div>
        );
      })}
    </dl>
  );
}
