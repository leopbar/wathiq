import { Fragment, useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Download, ScrollText } from "lucide-react";
import { apiFetch, apiUrl, buildQuery, withToken } from "@/lib/api";
import { qk } from "@/lib/query";
import type { AuditEntry, Page } from "@/lib/types";
import { PAGE_SIZE } from "@/lib/constants";
import { formatDateTime } from "@/lib/format";
import { useDebounced } from "@/lib/useDebounced";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { TableSkeleton } from "@/components/Skeletons";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/input";
import { SearchInput } from "@/components/ui/search-input";
import { Table, TableWrap, Td, Th, Tr } from "@/components/ui/table";
import { Pagination } from "@/components/ui/pagination";

const ACTOR_TONE = {
  agent: "primary",
  user: "info",
  system: "neutral",
} as const;

export default function AuditLog() {
  const [search, setSearch] = useState("");
  const [actor, setActor] = useState("");
  const [action, setAction] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<string | null>(null);

  const q = useDebounced(search, 300);
  const debouncedActor = useDebounced(actor, 300);
  const debouncedAction = useDebounced(action, 300);

  const params = useMemo(
    () => ({
      q,
      actor: debouncedActor,
      action: debouncedAction,
      date_from: dateFrom,
      date_to: dateTo,
      page,
      size: PAGE_SIZE,
    }),
    [q, debouncedActor, debouncedAction, dateFrom, dateTo, page],
  );

  const query = useQuery({
    queryKey: qk.audit(params),
    queryFn: () => apiFetch<Page<AuditEntry>>(`/audit${buildQuery(params)}`),
    placeholderData: keepPreviousData,
  });

  // A download link cannot send an Authorization header, so the token rides in the query string.
  const exportHref = withToken(
    apiUrl(
      `/audit/export${buildQuery({ ...params, format: "csv", page: undefined, size: undefined })}`,
    ),
  );

  const clearFilters = () => {
    setSearch("");
    setActor("");
    setAction("");
    setDateFrom("");
    setDateTo("");
    setPage(1);
  };

  const hasFilters = Boolean(q || debouncedActor || debouncedAction || dateFrom || dateTo);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Audit log"
        description="An append-only record of every action: who or what did it, when, and which prompt and model version were pinned at the time."
        actions={
          <a
            href={exportHref}
            className={buttonVariants({ variant: "secondary", size: "sm" })}
            download
          >
            <Download className="h-3.5 w-3.5" aria-hidden />
            Export CSV
          </a>
        }
      />

      <Card className="p-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <div className="xl:col-span-2">
            <Field label="Search" htmlFor="audit-q">
              <SearchInput
                id="audit-q"
                value={search}
                onChange={(value) => {
                  setSearch(value);
                  setPage(1);
                }}
                placeholder="Free text across labels and references…"
                ariaLabel="Search the audit log"
              />
            </Field>
          </div>
          <Field label="Actor" htmlFor="audit-actor">
            <Input
              id="audit-actor"
              value={actor}
              onChange={(e) => {
                setActor(e.target.value);
                setPage(1);
              }}
              placeholder="supervisor_node"
            />
          </Field>
          <Field label="Action" htmlFor="audit-action">
            <Input
              id="audit-action"
              value={action}
              onChange={(e) => {
                setAction(e.target.value);
                setPage(1);
              }}
              placeholder="document.classified"
            />
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label="From" htmlFor="audit-from">
              <Input
                id="audit-from"
                type="date"
                value={dateFrom}
                onChange={(e) => {
                  setDateFrom(e.target.value);
                  setPage(1);
                }}
              />
            </Field>
            <Field label="To" htmlFor="audit-to">
              <Input
                id="audit-to"
                type="date"
                value={dateTo}
                onChange={(e) => {
                  setDateTo(e.target.value);
                  setPage(1);
                }}
              />
            </Field>
          </div>
        </div>
        {hasFilters ? (
          <div className="mt-3 flex justify-end">
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              Clear filters
            </Button>
          </div>
        ) : null}
      </Card>

      {query.isPending ? (
        <TableSkeleton rows={10} cols={6} />
      ) : query.isError ? (
        <Card>
          <ErrorState error={query.error} onRetry={() => void query.refetch()} />
        </Card>
      ) : query.data.items.length === 0 ? (
        <Card>
          <EmptyState
            icon={ScrollText}
            title={hasFilters ? "No entries match these filters" : "The audit log is empty"}
            description={
              hasFilters
                ? "Widen the date range or clear the actor and action filters."
                : "Entries appear as soon as the pipeline or a reviewer acts on a case."
            }
            action={
              hasFilters ? (
                <Button variant="secondary" size="sm" onClick={clearFilters}>
                  Clear filters
                </Button>
              ) : undefined
            }
          />
        </Card>
      ) : (
        <div className="rounded-[var(--radius-lg)] border border-border bg-surface">
          <TableWrap className="rounded-b-none border-0">
            <Table>
              <caption className="sr-only">Audit entries</caption>
              <thead>
                <tr>
                  <Th className="w-8">
                    <span className="sr-only">Expand</span>
                  </Th>
                  <Th>When</Th>
                  <Th>Actor</Th>
                  <Th>Action</Th>
                  <Th>Case</Th>
                  <Th>Prompt</Th>
                  <Th>Model</Th>
                </tr>
              </thead>
              <tbody>
                {query.data.items.map((entry) => {
                  const open = expanded === entry.id;
                  return (
                    <Fragment key={entry.id}>
                      <Tr clickable onClick={() => setExpanded(open ? null : entry.id)}>
                        <Td>
                          <button
                            type="button"
                            aria-expanded={open}
                            aria-label={open ? "Hide detail" : "Show detail"}
                            className="text-ink-2"
                            onClick={(e) => {
                              e.stopPropagation();
                              setExpanded(open ? null : entry.id);
                            }}
                          >
                            {open ? (
                              <ChevronDown className="h-4 w-4" aria-hidden />
                            ) : (
                              <ChevronRight className="h-4 w-4 rtl:rotate-180" aria-hidden />
                            )}
                          </button>
                        </Td>
                        <Td className="whitespace-nowrap text-small text-ink-2">
                          {formatDateTime(entry.created_at)}
                        </Td>
                        <Td>
                          <div className="flex items-center gap-2">
                            <Badge tone={ACTOR_TONE[entry.actor_type]}>{entry.actor_type}</Badge>
                            <span className="truncate text-small text-ink">{entry.actor}</span>
                          </div>
                        </Td>
                        <Td>
                          <div className="min-w-0">
                            <p className="truncate text-small text-ink">{entry.label}</p>
                            <code className="text-caption text-ink-2">{entry.action}</code>
                          </div>
                        </Td>
                        <Td className="whitespace-nowrap text-small tabular">
                          {entry.case_reference ?? "—"}
                        </Td>
                        <Td className="whitespace-nowrap text-caption text-ink-2">
                          {entry.prompt_version ?? "—"}
                        </Td>
                        <Td className="whitespace-nowrap text-caption text-ink-2">
                          {entry.model_version ?? "—"}
                        </Td>
                      </Tr>
                      {open ? (
                        <tr className="bg-surface-2/60">
                          <td colSpan={7} className="border-b border-border px-4 py-3">
                            <div className="flex flex-wrap gap-4">
                              <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-caption">
                                <dt className="text-ink-2">Entry id</dt>
                                <dd className="text-ink tabular" dir="ltr">
                                  {entry.id}
                                </dd>
                                <dt className="text-ink-2">IP address</dt>
                                <dd className="text-ink tabular" dir="ltr">
                                  {entry.ip_address ?? "—"}
                                </dd>
                                <dt className="text-ink-2">Case id</dt>
                                <dd className="text-ink tabular" dir="ltr">
                                  {entry.case_id ?? "—"}
                                </dd>
                              </dl>
                              <pre
                                dir="ltr"
                                className="scroll-thin max-h-56 flex-1 overflow-auto rounded-[var(--radius-sm)] border border-border bg-surface p-3 text-caption leading-5"
                              >
                                {JSON.stringify(entry.detail ?? {}, null, 2)}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  );
                })}
              </tbody>
            </Table>
          </TableWrap>
          <Pagination
            page={query.data.page}
            pages={query.data.pages}
            total={query.data.total}
            size={query.data.size}
            onPageChange={setPage}
            label="entries"
          />
        </div>
      )}
    </div>
  );
}
