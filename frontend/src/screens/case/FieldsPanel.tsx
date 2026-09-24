import { AlertCircle, Crosshair, Languages, ShieldAlert } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { Document, ExtractedField, FieldStatus } from "@/lib/types";
import { cn } from "@/lib/cn";
import { Badge } from "@/components/ui/badge";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { EmptyState } from "@/components/EmptyState";
import { Tooltip } from "@/components/ui/tooltip";
import { ConfidenceSignals } from "./ConfidenceSignals";

const STATUS_TONE: Record<FieldStatus, "success" | "warning" | "info" | "danger"> = {
  auto_accepted: "success",
  needs_review: "warning",
  corrected: "info",
  rejected: "danger",
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
  const { t, i18n } = useTranslation();
  const arabic = i18n.language.startsWith("ar");
  if (fields.length === 0) {
    return (
      <EmptyState
        title={t("caseDetail.fields.empty")}
        description={t("caseDetail.fields.emptyDescription")}
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
            {group.document
              ? t(`catalog.docType.${group.document.doc_type}`, {
                  defaultValue: group.document.doc_type_label,
                })
              : t("caseDetail.fields.crossDocument")}
          </h3>
          <ul className="divide-y divide-border">
            {group.fields.map((field) => {
              const active = field.id === selectedFieldId;
              const value = field.corrected_value ?? field.value;
              // A translation is a reading aid, so it leads only when the reader cannot read
              // the original — and the document's own words always stay on screen beneath it.
              const translated =
                !arabic && !field.corrected_value ? field.value_translated : null;
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
                            <Tooltip content={t("caseDetail.fields.criticalHint")}>
                              <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-danger" />
                            </Tooltip>
                          ) : null}
                          <span className="truncate">{arabic ? field.label_ar : field.label_en}</span>
                        </p>
                        <p className="truncate text-caption text-ink-2" dir={arabic ? "ltr" : "rtl"}>
                          {arabic ? field.label_en : field.label_ar}
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
                      {translated ? (
                        <bdi>{translated}</bdi>
                      ) : value ? (
                        <bdi>{value}</bdi>
                      ) : (
                        t("caseDetail.fields.notFound")
                      )}
                    </p>

                    {translated && value ? (
                      <p className="mt-0.5 break-words text-caption text-ink-2" dir="rtl">
                        <bdi>{value}</bdi>
                      </p>
                    ) : null}

                    {field.corrected_value && field.value ? (
                      <p className="mt-0.5 text-caption text-ink-2 line-through">
                        <bdi>{field.value}</bdi>
                      </p>
                    ) : null}

                    <div className="mt-2 flex flex-wrap items-center gap-1.5">
                      <Badge tone={STATUS_TONE[field.status]}>{t(`caseDetail.fields.status.${field.status}`)}</Badge>
                      {field.bbox ? (
                        <Badge tone="outline">
                          <Crosshair className="h-3 w-3" aria-hidden />
                          {t("caseDetail.fields.page", { page: field.page ?? 1 })}
                        </Badge>
                      ) : (
                        <Badge tone="outline">
                          <AlertCircle className="h-3 w-3" aria-hidden />
                          {t("caseDetail.fields.noSourceRegion")}
                        </Badge>
                      )}
                      {translated ? (
                        <Tooltip content={t("caseDetail.fields.translationHint")}>
                          <Badge tone="outline">
                            <Languages className="h-3 w-3" aria-hidden />
                            {t(`caseDetail.fields.translatedBy.${field.translation_source}`, {
                              defaultValue: t("caseDetail.fields.translatedBy.model"),
                            })}
                          </Badge>
                        </Tooltip>
                      ) : null}
                      <code className="text-caption text-ink-2/80" dir="ltr">
                        {field.name}
                      </code>
                    </div>

                    {active && field.signals && field.signals.length > 0 ? (
                      <div className="mt-3 border-t border-border pt-3">
                        <p className="label-caption mb-1.5 text-ink-2">{t("caseDetail.fields.whyConfidence")}</p>
                        <ConfidenceSignals signals={field.signals} />
                      </div>
                    ) : null}
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
