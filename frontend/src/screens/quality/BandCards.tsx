import type { LucideIcon } from "lucide-react";
import { Bot, Brain, ShieldCheck, Swords, TerminalSquare } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { QualityBand } from "@/lib/types";
import { formatNumber, formatPercent, formatRelative } from "@/lib/format";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";

const BAND_ICON: Record<string, LucideIcon> = {
  model: Brain,
  prompt: TerminalSquare,
  agent: Bot,
  ai_security: ShieldCheck,
  security: ShieldCheck,
  adversarial: Swords,
};

export function BandCardsSkeleton() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {[0, 1, 2, 3, 4].map((i) => (
        <Card key={i} className="p-4">
          <Skeleton className="h-4 w-24" />
          <Skeleton className="mt-4 h-7 w-16" />
          <Skeleton className="mt-4 h-1.5 w-full" />
        </Card>
      ))}
    </div>
  );
}

export function BandCards({
  bands,
  selected,
  onSelect,
}: {
  bands: QualityBand[];
  selected: string;
  onSelect: (band: string) => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {bands.map((band) => {
        const Icon = BAND_ICON[band.band] ?? Brain;
        const failing = band.failed > 0;
        const active = selected === band.band;
        const label = t(`quality.band.${band.band}.label`, { defaultValue: band.label });
        return (
          <Card
            key={band.band}
            className={active ? "border-primary/50 ring-1 ring-primary/30" : undefined}
          >
            <button
              type="button"
              onClick={() => onSelect(active ? "all" : band.band)}
              aria-pressed={active}
              className="w-full p-4 text-start"
            >
              <div className="flex items-start justify-between gap-2">
                <span className="flex h-8 w-8 items-center justify-center rounded-[var(--radius-sm)] bg-surface-2 text-ink-2">
                  <Icon className="h-4 w-4" aria-hidden />
                </span>
                <Badge tone={failing ? "danger" : "success"}>
                  {failing
                    ? t("quality.bandFailed", { count: band.failed })
                    : t("quality.allPassed")}
                </Badge>
              </div>
              <p className="mt-3 text-body font-semibold text-ink">{label}</p>
              <p className="mt-0.5 text-caption leading-4 text-ink-2">
                {t(`quality.band.${band.band}.blurb`, { defaultValue: t("quality.evaluationBand") })}
              </p>
              <p className="mt-3 text-h1 font-semibold text-ink tabular">
                {formatPercent(band.score, 1)}
              </p>
              <Progress
                className="mt-2"
                value={band.score * 100}
                label={t("quality.bandScore", { band: label })}
                tone={band.score >= 0.9 ? "success" : band.score >= 0.75 ? "warning" : "danger"}
              />
              <p className="mt-2 text-caption text-ink-2 tabular">
                {t("quality.bandCases", {
                  passed: formatNumber(band.passed),
                  total: formatNumber(band.total),
                })}{" "}
                · {formatRelative(band.last_run_at)}
              </p>
            </button>
          </Card>
        );
      })}
    </div>
  );
}
