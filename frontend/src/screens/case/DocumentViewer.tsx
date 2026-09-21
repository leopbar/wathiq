import { useState } from "react";
import { ExternalLink, FileWarning, Maximize2, Minus, Plus, RotateCw } from "lucide-react";
import type { Document, ExtractedField } from "@/lib/types";
import { withToken } from "@/lib/api";
import { formatBytes, formatPercent } from "@/lib/format";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { EmptyState } from "@/components/EmptyState";

/**
 * M1 viewer: the raw file in an iframe plus a normalised bounding-box overlay
 * for the selected field. react-pdf replaces the iframe in M2, which is why the
 * toolbar already carries zoom and page controls.
 */
export function DocumentViewer({
  document,
  highlighted,
  className,
}: {
  document: Document | null;
  highlighted: ExtractedField | null;
  className?: string;
}) {
  const [zoom, setZoom] = useState(1);
  const [page, setPage] = useState(1);
  const [imageRatios, setImageRatios] = useState<Record<string, number>>({});

  if (!document) {
    return (
      <div className={className}>
        <EmptyState
          icon={FileWarning}
          title="No document selected"
          description="Pick a document on the left to preview it here."
        />
      </div>
    );
  }

  const bbox = highlighted?.bbox ?? null;
  const currentPage = Math.min(Math.max(page, 1), Math.max(document.page_count, 1));
  const isImage = document.mime_type.startsWith("image/");
  const previewUrl = withToken(document.preview_url);
  const previewAspectRatio = isImage
    ? (imageRatios[document.id] ?? 1)
    : "1 / 1.414";

  return (
    <div className={className}>
      <div className="flex flex-wrap items-center gap-2 border-b border-border bg-surface-2/60 px-3 py-2">
        <div className="min-w-0 flex-1">
          <p className="truncate text-small font-medium text-ink">{document.filename}</p>
          <p className="truncate text-caption text-ink-2">
            {document.doc_type_label} · {formatBytes(document.size_bytes)} ·{" "}
            {document.page_count} page{document.page_count === 1 ? "" : "s"}
          </p>
        </div>

        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="iconSm"
            aria-label="Previous page"
            disabled={currentPage <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            <Minus className="h-3.5 w-3.5" aria-hidden />
          </Button>
          <span className="text-caption text-ink-2 tabular">
            {currentPage}/{Math.max(document.page_count, 1)}
          </span>
          <Button
            variant="ghost"
            size="iconSm"
            aria-label="Next page"
            disabled={currentPage >= document.page_count}
            onClick={() => setPage((p) => p + 1)}
          >
            <Plus className="h-3.5 w-3.5" aria-hidden />
          </Button>
          <span className="mx-1 h-4 w-px bg-border" aria-hidden />
          <Button
            variant="ghost"
            size="iconSm"
            aria-label="Zoom out"
            disabled={zoom <= 0.6}
            onClick={() => setZoom((z) => Math.max(0.6, Number((z - 0.2).toFixed(1))))}
          >
            <Minus className="h-3.5 w-3.5" aria-hidden />
          </Button>
          <span className="text-caption text-ink-2 tabular">{Math.round(zoom * 100)}%</span>
          <Button
            variant="ghost"
            size="iconSm"
            aria-label="Zoom in"
            disabled={zoom >= 2}
            onClick={() => setZoom((z) => Math.min(2, Number((z + 0.2).toFixed(1))))}
          >
            <Plus className="h-3.5 w-3.5" aria-hidden />
          </Button>
          <Button variant="ghost" size="iconSm" aria-label="Reset zoom" onClick={() => setZoom(1)}>
            <RotateCw className="h-3.5 w-3.5" aria-hidden />
          </Button>
          <Tooltip content="Open the raw file in a new tab">
            <a
              href={previewUrl}
              target="_blank"
              rel="noreferrer"
              aria-label="Open document in a new tab"
              className="inline-flex h-8 w-8 items-center justify-center rounded-[var(--radius)] text-ink-2 hover:bg-surface-2 hover:text-ink"
            >
              <ExternalLink className="h-3.5 w-3.5" aria-hidden />
            </a>
          </Tooltip>
        </div>
      </div>

      <div className="relative flex-1 overflow-auto scroll-thin bg-surface-2/40 p-3">
        <div
          className="relative mx-auto bg-surface shadow-card"
          style={{ width: `${Math.round(zoom * 100)}%`, aspectRatio: previewAspectRatio }}
        >
          {isImage ? (
            <img
              key={document.id}
              src={previewUrl}
              alt={`Preview of ${document.filename}`}
              className="absolute inset-0 h-full w-full rounded-[var(--radius-sm)] object-contain"
              onLoad={(event) => {
                const { naturalWidth, naturalHeight } = event.currentTarget;
                if (naturalWidth > 0 && naturalHeight > 0) {
                  setImageRatios((ratios) => ({
                    ...ratios,
                    [document.id]: naturalWidth / naturalHeight,
                  }));
                }
              }}
            />
          ) : (
            <iframe
              key={`${document.id}-${currentPage}`}
              src={`${previewUrl}#page=${currentPage}&view=FitH`}
              title={`Preview of ${document.filename}`}
              className="absolute inset-0 h-full w-full rounded-[var(--radius-sm)] border-0"
            />
          )}
          {bbox ? (
            <div
              className="pointer-events-none absolute rounded-[3px] border-2 border-warning bg-warning/15 shadow-[0_0_0_9999px_rgba(11,18,32,0.18)]"
              style={{
                left: `${bbox[0] * 100}%`,
                top: `${bbox[1] * 100}%`,
                width: `${bbox[2] * 100}%`,
                height: `${bbox[3] * 100}%`,
              }}
              aria-hidden
            />
          ) : null}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-border px-3 py-2">
        {highlighted ? (
          <>
            <Maximize2 className="h-3.5 w-3.5 text-warning" aria-hidden />
            <span className="text-caption text-ink-2">
              Showing source region for{" "}
              <span className="font-medium text-ink">{highlighted.label_en}</span>
            </span>
            {highlighted.source_text ? (
              <span className="truncate text-caption text-ink-2 italic">
                “{highlighted.source_text}”
              </span>
            ) : null}
          </>
        ) : (
          <span className="text-caption text-ink-2">
            Select a field to highlight where it came from.
          </span>
        )}
        <span className="ms-auto flex items-center gap-1.5">
          {document.ocr_confidence !== null ? (
            <Badge tone="outline">OCR {formatPercent(document.ocr_confidence)}</Badge>
          ) : null}
          {document.classification_confidence !== null ? (
            <Badge tone="outline">
              Class {formatPercent(document.classification_confidence)}
            </Badge>
          ) : null}
        </span>
      </div>
    </div>
  );
}
