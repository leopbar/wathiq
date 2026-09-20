import { RotateCcw, ShieldAlert } from "lucide-react";
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
  if (fields.length === 0) {
    return (
      <EmptyState
        title="No fields to review"
        description="This task has no extracted fields attached."
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
                aria-label={`Show source region for ${field.label_en}`}
              >
                <p className="flex items-center gap-1.5 text-small font-medium text-ink">
                  {field.is_critical ? (
                    <Tooltip content="Critical field">
                      <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-danger" />
                    </Tooltip>
                  ) : null}
                  <span className="truncate">{field.label_en}</span>
                </p>
                <p className="truncate text-caption text-ink-2" dir="rtl">
                  {field.label_ar}
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
                aria-label={`Value for ${field.label_en}`}
                onFocus={() => onSelectField(field)}
                onChange={(e) => onDraftChange(field.id, e.target.value)}
                className={cn(changed && "border-info")}
              />
              {changed ? (
                <Button
                  variant="ghost"
                  size="iconSm"
                  aria-label={`Undo correction to ${field.label_en}`}
                  onClick={() => onDraftChange(field.id, undefined)}
                >
                  <RotateCcw className="h-3.5 w-3.5" aria-hidden />
                </Button>
              ) : null}
            </div>

            {changed ? (
              <p className="mt-1 text-caption text-info">
                Was <span className="line-through">{original || "empty"}</span>
              </p>
            ) : null}

            {field.source_text ? (
              <p className="mt-1.5 truncate text-caption italic text-ink-2">
                “{field.source_text}”
              </p>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
