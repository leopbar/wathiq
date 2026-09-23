import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/cn";
import { SortableTh, Table, TableWrap, Td, Th, Tr } from "./ui/table";
import { TableSkeleton } from "./Skeletons";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";

export interface Column<T> {
  key: string;
  header: string;
  /** Backend sort field; omit to make the column unsortable. */
  sortField?: string;
  cell: (row: T) => ReactNode;
  className?: string;
  headerClassName?: string;
  /** Hidden in the responsive card layout. */
  hideOnCard?: boolean;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  isPending?: boolean;
  isError?: boolean;
  error?: unknown;
  onRetry?: () => void;
  onRowClick?: (row: T) => void;
  sort?: string;
  onSortChange?: (sort: string) => void;
  empty?: ReactNode;
  caption: string;
  footer?: ReactNode;
  /** Headline shown at the top of each card in the < 768px layout. */
  cardTitle?: (row: T) => ReactNode;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  isPending,
  isError,
  error,
  onRetry,
  onRowClick,
  sort,
  onSortChange,
  empty,
  caption,
  footer,
  cardTitle,
}: DataTableProps<T>) {
  const { t } = useTranslation();
  if (isPending) return <TableSkeleton cols={Math.min(columns.length, 7)} />;

  if (isError) {
    return (
      <TableWrap>
        <ErrorState error={error} onRetry={onRetry} />
      </TableWrap>
    );
  }

  if (rows.length === 0) {
    return (
      <TableWrap>
        {empty ?? <EmptyState title={t("common.nothingToShow")} description={t("common.noRecords")} />}
      </TableWrap>
    );
  }

  return (
    <div className="rounded-[var(--radius-lg)] border border-border bg-surface">
      {/* Table layout — 768px and up */}
      <div className="scroll-thin hidden overflow-x-auto md:block">
        <Table>
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr>
              {columns.map((column) =>
                column.sortField && sort !== undefined && onSortChange ? (
                  <SortableTh
                    key={column.key}
                    label={column.header}
                    field={column.sortField}
                    sort={sort}
                    onSort={onSortChange}
                    className={column.headerClassName}
                  />
                ) : (
                  <Th key={column.key} className={column.headerClassName}>
                    {column.header}
                  </Th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <Tr
                key={rowKey(row)}
                clickable={Boolean(onRowClick)}
                tabIndex={onRowClick ? 0 : undefined}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                onKeyDown={
                  onRowClick
                    ? (e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          onRowClick(row);
                        }
                      }
                    : undefined
                }
              >
                {columns.map((column) => (
                  <Td key={column.key} className={column.className}>
                    {column.cell(row)}
                  </Td>
                ))}
              </Tr>
            ))}
          </tbody>
        </Table>
      </div>

      {/* Card layout — under 768px */}
      <ul className="divide-y divide-border md:hidden">
        {rows.map((row) => (
          <li key={rowKey(row)}>
            <div
              role={onRowClick ? "button" : undefined}
              tabIndex={onRowClick ? 0 : undefined}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              onKeyDown={
                onRowClick
                  ? (e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        onRowClick(row);
                      }
                    }
                  : undefined
              }
              className={cn("px-4 py-3.5", onRowClick && "cursor-pointer active:bg-surface-2")}
            >
              {cardTitle ? <div className="mb-2">{cardTitle(row)}</div> : null}
              <dl className="grid grid-cols-2 gap-x-3 gap-y-2">
                {columns
                  .filter((c) => !c.hideOnCard)
                  .map((column) => (
                    <div key={column.key} className="min-w-0">
                      <dt className="label-caption text-ink-2">{column.header}</dt>
                      <dd className="mt-0.5 truncate text-small text-ink">{column.cell(row)}</dd>
                    </div>
                  ))}
              </dl>
            </div>
          </li>
        ))}
      </ul>

      {footer}
    </div>
  );
}
