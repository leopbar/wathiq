import { FileText, Image as ImageIcon, Languages } from "lucide-react";
import type { Document } from "@/lib/types";
import { formatBytes } from "@/lib/format";
import { cn } from "@/lib/cn";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/EmptyState";

const LANGUAGE_LABEL: Record<Document["language"], string> = {
  en: "EN",
  ar: "AR",
  mixed: "EN/AR",
};

const STATUS_TONE: Record<Document["status"], "neutral" | "info" | "success" | "danger"> = {
  uploaded: "neutral",
  ocr: "info",
  classified: "info",
  extracted: "success",
  failed: "danger",
};

export function DocumentList({
  documents,
  selectedId,
  onSelect,
}: {
  documents: Document[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  if (documents.length === 0) {
    return <EmptyState title="No documents" description="This case has no files attached." />;
  }

  return (
    <ul className="divide-y divide-border">
      {documents.map((document) => {
        const active = document.id === selectedId;
        const Icon = document.mime_type.startsWith("image/") ? ImageIcon : FileText;
        return (
          <li key={document.id}>
            <button
              type="button"
              onClick={() => onSelect(document.id)}
              aria-current={active}
              className={cn(
                "flex w-full gap-3 px-4 py-3 text-start transition-colors",
                active ? "bg-primary-soft/60" : "hover:bg-surface-2/70",
              )}
            >
              <span
                className={cn(
                  "flex h-11 w-9 shrink-0 items-center justify-center rounded-[var(--radius-sm)] border",
                  active
                    ? "border-primary/40 bg-surface text-primary"
                    : "border-border bg-surface-2 text-ink-2",
                )}
              >
                <Icon className="h-4 w-4" aria-hidden />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-small font-medium text-ink">
                  {document.doc_type_label}
                </span>
                <span className="block truncate text-caption text-ink-2">{document.filename}</span>
                <span className="mt-1.5 flex flex-wrap items-center gap-1">
                  <Badge tone={STATUS_TONE[document.status]}>{document.status}</Badge>
                  <Badge tone="outline">
                    <Languages className="h-3 w-3" aria-hidden />
                    {LANGUAGE_LABEL[document.language]}
                  </Badge>
                  <span className="text-caption text-ink-2 tabular">
                    {formatBytes(document.size_bytes)}
                  </span>
                </span>
              </span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
