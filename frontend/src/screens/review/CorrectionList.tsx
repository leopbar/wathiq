import { RotateCcw, ShieldAlert } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { ExtractedField } from "@/lib/types";
import { cn } from "@/lib/cn";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { EmptyState } from "@/components/EmptyState";

export function CorrectionList({
  fields,
  drafts,
  onDraftChange,
  selectedFieldId,
  onSelectField,
  disabled,
}: {
  fields: ExtractedField[];
  drafts: Record<string, string>;
  onDraftChange: (fieldId: string, value: string | undefined) => void;
  selectedFieldId: string | null;
  onSelectField: (field: ExtractedField) => void;
  disabled: boolean;
}) {
  const { t, i18n } = useTranslation();
  const arabic = i18n.language.startsWith("ar");
  if (fields.length === 0) {
    return (
      <EmptyState
        title={t("reviewTask.corrections.empty")}
        description={t("reviewTask.corrections.emptyDescription")}
      />
    );
  }

  return (
    <ul className="divide-y divide-border">
      {fields.map((field) => {
        const original = field.corrected_value ?? field.value ?? "";
        const draft = drafts[field.id];
        const changed = draft !== undefined && draft !== original;
        const active = field.id === selectedFieldId;
        const label = arabic && field.label_ar ? field.label_ar : field.label_en;

        return (
          <li
            key={field.id}
            className={cn("px-4 py-3 transition-colors", active && "bg-primary-soft/40")}
          >
            <div className="flex items-start justify-between gap-3">
              <button
                type="button"
                onClick={() => onSelectField(field)}
                className="min-w-0 flex-1 text-start"
                aria-label={t("reviewTask.corrections.showRegion", { label })}
              >
                <p className="flex items-center gap-1.5 text-small font-medium text-ink">
                  {field.is_critical ? (
                    <Tooltip content={t("reviewTask.corrections.critical")}>
                      <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-danger" />
                    </Tooltip>
                  ) : null}
                  <span className="truncate">{label}</span>
                </p>
                <p className="truncate text-caption text-ink-2" dir={arabic ? "ltr" : "rtl"}>
                  {arabic ? field.label_en : field.label_ar}
                </p>
              </button>
              <ConfidenceBadge
                value={field.calibrated_confidence}
                raw={field.confidence}
                showLabel={false}
              />
            </div>

            <div className="mt-2 flex items-center gap-2">
              <Input
                value={draft ?? original}
                disabled={disabled}
                aria-label={t("reviewTask.corrections.valueFor", { label })}
                onFocus={() => onSelectField(field)}
                onChange={(e) => onDraftChange(field.id, e.target.value)}
                className={cn(changed && "border-info")}
              />
              {changed ? (
                <Button
                  variant="ghost"
                  size="iconSm"
                  aria-label={t("reviewTask.corrections.undo", { label })}
                  onClick={() => onDraftChange(field.id, undefined)}
                >
                  <RotateCcw className="h-3.5 w-3.5" aria-hidden />
                </Button>
              ) : null}
            </div>

            {!arabic && field.value_translated && !changed ? (
              // The box holds the document's own words, because that is what gets saved. The
              // English sits beneath it, so a reviewer who does not read Arabic still knows
              // what they are approving.
              <p className="mt-1 text-caption text-ink-2">
                {t("reviewTask.corrections.inEnglish")}{" "}
                <span className="text-ink">{field.value_translated}</span>
              </p>
            ) : null}

            {changed ? (
              <p className="mt-1 text-caption text-info">
                {t("reviewTask.corrections.was")}{" "}
                <span className="line-through">
                  <bdi>{original || t("reviewTask.corrections.emptyValue")}</bdi>
                </span>
              </p>
            ) : null}

            {field.source_text ? (
              <p className="mt-1.5 truncate text-caption italic text-ink-2">
                “<bdi>{field.source_text}</bdi>”
              </p>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
