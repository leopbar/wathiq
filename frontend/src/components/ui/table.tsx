import type { HTMLAttributes, ReactNode, ThHTMLAttributes } from "react";
import { ArrowDown, ArrowUp, ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/cn";

export function TableWrap({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "scroll-thin overflow-x-auto rounded-[var(--radius-lg)] border border-border bg-surface",
        className,
      )}
      {...props}
    />
  );
}

export function Table({ className, ...props }: HTMLAttributes<HTMLTableElement>) {
  return <table className={cn("w-full border-collapse text-body", className)} {...props} />;
}

export function Th({
  className,
  children,
  ...props
}: ThHTMLAttributes<HTMLTableCellElement> & { children?: ReactNode }) {
  return (
    <th
      scope="col"
      className={cn(
        "label-caption sticky top-0 z-10 whitespace-nowrap border-b border-border bg-surface-2 px-3 py-2.5 text-start text-ink-2",
        className,
      )}
      {...props}
    >
      {children}
    </th>
  );
}

export function SortableTh({
  label,
  field,
  sort,
  onSort,
  className,
}: {
  label: string;
  field: string;
  sort: string;
  onSort: (next: string) => void;
  className?: string;
}) {
  const active = sort === field || sort === `-${field}`;
  const descending = sort === `-${field}`;
  const next = active && descending ? field : `-${field}`;

  return (
    <Th
      className={className}
      aria-sort={active ? (descending ? "descending" : "ascending") : "none"}
    >
      <button
        type="button"
        onClick={() => onSort(next)}
        className="inline-flex items-center gap-1 rounded-[var(--radius-sm)] hover:text-ink"
      >
        {label}
        {active ? (
          descending ? (
            <ArrowDown className="h-3 w-3" aria-hidden />
          ) : (
            <ArrowUp className="h-3 w-3" aria-hidden />
          )
        ) : (
          <ChevronsUpDown className="h-3 w-3 opacity-50" aria-hidden />
        )}
      </button>
    </Th>
  );
}

export function Td({ className, ...props }: HTMLAttributes<HTMLTableCellElement>) {
  return (
    <td
      className={cn("border-b border-border px-3 py-2.5 align-middle text-ink", className)}
      {...props}
    />
  );
}

export function Tr({
  className,
  clickable,
  ...props
}: HTMLAttributes<HTMLTableRowElement> & { clickable?: boolean }) {
  return (
    <tr
      className={cn(
        "transition-colors last:[&>td]:border-b-0",
        clickable && "cursor-pointer hover:bg-surface-2/70 focus-visible:bg-surface-2",
        className,
      )}
      {...props}
    />
  );
}
