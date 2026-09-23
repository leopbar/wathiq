import { ArrowUpRight, Check, Keyboard, PencilLine, X } from "lucide-react";
import type { ReasonCode, ReviewDecision } from "@/lib/types";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Tooltip } from "@/components/ui/tooltip";

const DECISION_ICON = {
  approve: Check,
  correct: PencilLine,
  reject: X,
  escalate: ArrowUpRight,
} as const;

const DECISIONS: ReviewDecision[] = ["approve", "correct", "reject", "escalate"];

const DECISION_KEY: Record<ReviewDecision, string> = {
  approve: "A",
  correct: "C",
  reject: "R",
  escalate: "E",
};

export function DecisionBar({
  decision,
  onDecisionChange,
  reasonCodes,
  reasonCode,
  onReasonCodeChange,
  note,
  onNoteChange,
  onSubmit,
  submitting,
  disabled,
  correctionCount,
  onOpenHelp,
}: {
  decision: ReviewDecision | null;
  onDecisionChange: (decision: ReviewDecision) => void;
  reasonCodes: ReasonCode[];
  reasonCode: string;
  onReasonCodeChange: (code: string) => void;
  note: string;
  onNoteChange: (note: string) => void;
  onSubmit: () => void;
  submitting: boolean;
  disabled: boolean;
  correctionCount: number;
  onOpenHelp: () => void;
}) {
  const { t } = useTranslation();
  const applicable = decision
    ? reasonCodes.filter((code) => code.applies_to.includes(decision))
    : [];
  const reasonRequired = decision === "reject" || decision === "escalate";

  return (
    <div className="sticky bottom-0 z-10 border-t border-border bg-surface/95 px-4 py-3 backdrop-blur">
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label={t("reviewTask.decision.group")}>
          {DECISIONS.map((value) => {
            const Icon = DECISION_ICON[value];
            const selected = decision === value;
            return (
              <Button
                key={value}
                size="sm"
                disabled={disabled}
                variant={
                  selected
                    ? value === "reject"
                      ? "danger"
                      : "primary"
                    : "secondary"
                }
                aria-pressed={selected}
                onClick={() => onDecisionChange(value)}
              >
                <Icon className="h-3.5 w-3.5" aria-hidden />
                {t(`catalog.decision.${value}`)}
                <kbd className="ms-1 rounded border border-current/30 px-1 text-caption opacity-70">
                  {DECISION_KEY[value]}
                </kbd>
              </Button>
            );
          })}
        </div>

        <Select
          value={reasonCode || undefined}
          onValueChange={onReasonCodeChange}
          disabled={disabled || !decision || applicable.length === 0}
          ariaLabel={t("reviewTask.decision.reasonCode")}
          placeholder={
            decision ? t("reviewTask.decision.reasonPlaceholder") : t("reviewTask.decision.pickFirst")
          }
          className="w-full sm:w-64"
          options={applicable.map((code) => ({
            value: code.code,
            label: t(`reviewTask.reasonCodes.${code.code}`, { defaultValue: code.label }),
          }))}
        />

        <Input
          value={note}
          disabled={disabled}
          onChange={(e) => onNoteChange(e.target.value)}
          aria-label={t("reviewTask.decision.note")}
          placeholder={t("reviewTask.decision.notePlaceholder")}
          className="w-full flex-1 sm:w-auto sm:min-w-48"
        />

        <Tooltip content={t("reviewTask.decision.shortcutsHint")}>
          <Button variant="ghost" size="icon" onClick={onOpenHelp} aria-label={t("reviewTask.shortcuts.title")}>
            <Keyboard className="h-4 w-4" aria-hidden />
          </Button>
        </Tooltip>

        <Button
          variant="primary"
          loading={submitting}
          disabled={disabled || !decision || (reasonRequired && !reasonCode)}
          onClick={onSubmit}
        >
          {t("reviewTask.decision.submit")}
        </Button>
      </div>

      <p className="mt-1.5 text-caption text-ink-2" aria-live="polite">
        {decision
          ? [
              t("reviewTask.decision.selected", { decision: t(`catalog.decision.${decision}`) }),
              correctionCount > 0
                ? t("reviewTask.decision.corrections", { count: correctionCount })
                : null,
              reasonRequired && !reasonCode ? t("reviewTask.decision.reasonRequired") : null,
            ]
              .filter(Boolean)
              .join(" · ")
          : t("reviewTask.decision.chooseHint")}
      </p>
    </div>
  );
}
