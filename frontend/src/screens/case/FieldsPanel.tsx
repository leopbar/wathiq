import { AlertCircle, Crosshair, ShieldAlert } from "lucide-react";
import type { Document, ExtractedField, FieldStatus } from "@/lib/types";
import { cn } from "@/lib/cn";
import { Badge } from "@/components/ui/badge";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { EmptyState } from "@/components/EmptyState";
import { Tooltip } from "@/components/ui/tooltip";

const STATUS_TONE: Record<FieldStatus, "success" | "warning" | "info" | "danger"> = {
  auto_accepted: "success",
  needs_review: "warning",
  corrected: "info",
  rejected: "danger",
};

const STATUS_LABEL: Record<FieldStatus, string> = {
  auto_accepted: "Auto-accepted",
  needs_review: "Needs review",
  corrected: "Corrected",
  rejected: "Rejected",
};

export function FieldsPanel({
  fields,
  documents,
  selectedFieldId,
  onSelectField,
}: {
  fields: ExtractedField[];
  documents: Document[];
  selectedFieldId: string | null;
  onSelectField: (field: ExtractedField) => void;
}) {
  if (fields.length === 0) {
    return (
      <EmptyState
        title="No fields extracted yet"
        description="Fields appear once the extract node has run for this case."
      />
    );
  }

  const groups: { document: Document | null; fields: ExtractedField[] }[] = documents
    .map((document) => ({
      document: document as Document | null,
      fields: fields.filter((f) => f.document_id === document.id),
    }))
    .filter((group) => group.fields.length > 0);

  const orphans = fields.filter(
    (f) => !f.document_id || !documents.some((d) => d.id === f.document_id),
  );
  if (orphans.length > 0) groups.push({ document: null, fields: orphans });

  return (
    <div className="divide-y divide-border">
      {groups.map((group, index) => (
        <section key={group.document?.id ?? `orphan-${index}`}>
          <h3 className="label-caption sticky top-0 z-10 border-b border-border bg-surface-2 px-4 py-2 text-ink-2">
            {group.document?.doc_type_label ?? "Cross-document"}
          </h3>
          <ul className="divide-y divide-border">
            {group.fields.map((field) => {
              const active = field.id === selectedFieldId;
              const value = field.corrected_value ?? field.value;
              return (
                <li key={field.id}>
                  <button
                    type="button"
                    onClick={() => onSelectField(field)}
                    aria-current={active}
                    className={cn(
                      "w-full px-4 py-3 text-start transition-colors",
                      active ? "bg-primary-soft/60" : "hover:bg-surface-2/70",
                    )}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="flex items-center gap-1.5 text-small font-medium text-ink">
                          {field.is_critical ? (
                            <Tooltip content="Critical field — a wrong value here blocks the case.">
                              <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-danger" />
                            </Tooltip>
                          ) : null}
                          <span className="truncate">{field.label_en}</span>
                        </p>
                        <p className="truncate text-caption text-ink-2" dir="rtl">
                          {field.label_ar}
                        </p>
                      </div>
                      <ConfidenceBadge
                        value={field.calibrated_confidence}
                        raw={field.confidence}
                        showLabel={false}
                      />
                    </div>

                    <p
                      className={cn(
                        "mt-1.5 break-words text-body",
                        value ? "text-ink" : "text-ink-2 italic",
                      )}
                    >
                      {value ?? "not found"}
                    </p>

                    {field.corrected_value && field.value ? (
                      <p className="mt-0.5 text-caption text-ink-2 line-through">{field.value}</p>
                    ) : null}

                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      <Badge tone={STATUS_TONE[field.status]}>{STATUS_LABEL[field.status]}</Badge>
                      {field.bbox ? (
                        <Badge tone="outline">
                          <Crosshair className="h-3 w-3" aria-hidden />
                          page {field.page ?? 1}
                        </Badge>
                      ) : (
                        <Badge tone="outline">
                          <AlertCircle className="h-3 w-3" aria-hidden />
                          no source region
                        </Badge>
                      )}
                      <code className="text-caption text-ink-2/80">{field.name}</code>
                    </div>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
