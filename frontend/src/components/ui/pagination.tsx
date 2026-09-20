import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "./button";
import { formatNumber } from "@/lib/format";

export function Pagination({
  page,
  pages,
  total,
  size,
  onPageChange,
  label = "results",
}: {
  page: number;
  pages: number;
  total: number;
  size: number;
  onPageChange: (page: number) => void;
  label?: string;
}) {
  const first = total === 0 ? 0 : (page - 1) * size + 1;
  const last = Math.min(page * size, total);

  return (
    <nav
      aria-label="Pagination"
      className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-3"
    >
      <p className="text-small text-ink-2 tabular">
        {formatNumber(first)}–{formatNumber(last)} of {formatNumber(total)} {label}
      </p>
      <div className="flex items-center gap-2">
        <Button
          size="sm"
          variant="secondary"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          <ChevronLeft className="h-4 w-4 rtl:rotate-180" aria-hidden />
          Previous
        </Button>
        <span className="text-small text-ink-2 tabular">
          Page {formatNumber(page)} of {formatNumber(Math.max(pages, 1))}
        </span>
        <Button
          size="sm"
          variant="secondary"
          disabled={page >= pages}
          onClick={() => onPageChange(page + 1)}
        >
          Next
          <ChevronRight className="h-4 w-4 rtl:rotate-180" aria-hidden />
        </Button>
      </div>
    </nav>
  );
}
