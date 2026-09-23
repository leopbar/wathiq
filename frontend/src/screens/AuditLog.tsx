import { Fragment, useMemo, useState } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
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
        title={t("nav.audit")}
        description={t("audit.description")}
        actions={
          <a
            href={exportHref}
            className={buttonVariants({ variant: "secondary", size: "sm" })}
            download
          >
            <Download className="h-3.5 w-3.5" aria-hidden />
            {t("common.export")}
          </a>
        }
      />

      <Card className="p-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <div className="xl:col-span-2">
            <Field label={t("common.search")} htmlFor="audit-q">
              <SearchInput
                id="audit-q"
                value={search}
                onChange={(value) => {
                  setSearch(value);
                  setPage(1);
                }}
                placeholder={t("audit.searchPlaceholder")}
                ariaLabel={t("audit.searchLabel")}
              />
            </Field>
          </div>
          <Field label={t("audit.actor")} htmlFor="audit-actor">
            <Input
              id="audit-actor"
              value={actor}
              onChange={(e) => {
                setActor(e.target.value);
                setPage(1);
              }}
              placeholder="supervisor_node"
              dir="ltr"
            />
          </Field>
          <Field label={t("audit.action")} htmlFor="audit-action">
            <Input
              id="audit-action"
              value={action}
              onChange={(e) => {
                setAction(e.target.value);
                setPage(1);
              }}
              placeholder="document.classified"
              dir="ltr"
            />
          </Field>
          <div className="grid grid-cols-2 gap-2">
            <Field label={t("audit.from")} htmlFor="audit-from">
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
            <Field label={t("audit.to")} htmlFor="audit-to">
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
              {t("cases.clearFilters")}
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
            title={hasFilters ? t("audit.noMatches") : t("audit.empty")}
            description={
              hasFilters
                ? t("audit.noMatchesDescription")
                : t("audit.emptyDescription")
            }
            action={
              hasFilters ? (
                <Button variant="secondary" size="sm" onClick={clearFilters}>
                  {t("cases.clearFilters")}
                </Button>
              ) : undefined
            }
          />
        </Card>
      ) : (
        <div className="rounded-[var(--radius-lg)] border border-border bg-surface">
          <TableWrap className="rounded-b-none border-0">
            <Table>
              <caption className="sr-only">{t("audit.caption")}</caption>
              <thead>
                <tr>
                  <Th className="w-8">
                    <span className="sr-only">{t("audit.expand")}</span>
                  </Th>
                  <Th>{t("audit.columns.when")}</Th>
                  <Th>{t("audit.columns.actor")}</Th>
                  <Th>{t("audit.columns.action")}</Th>
                  <Th>{t("audit.columns.case")}</Th>
                  <Th>{t("audit.columns.prompt")}</Th>
                  <Th>{t("audit.columns.model")}</Th>
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
                            aria-label={open ? t("audit.hideDetail") : t("audit.showDetail")}
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
                            <Badge tone={ACTOR_TONE[entry.actor_type]}>{t(`audit.actorType.${entry.actor_type}`)}</Badge>
                            <bdi className="truncate text-small text-ink">
                              {entry.actor}
                            </bdi>
                          </div>
                        </Td>
                        <Td>
                          <div className="min-w-0">
                            <p className="truncate text-small text-ink">{entry.label}</p>
                            <code className="text-caption text-ink-2" dir="ltr">
                              {entry.action}
                            </code>
                          </div>
                        </Td>
                        <Td className="whitespace-nowrap text-small tabular">
                          <bdi>{entry.case_reference ?? "—"}</bdi>
                        </Td>
                        <Td className="whitespace-nowrap text-caption text-ink-2">
                          <bdi>{entry.prompt_version ?? "—"}</bdi>
                        </Td>
                        <Td className="whitespace-nowrap text-caption text-ink-2">
                          <bdi>{entry.model_version ?? "—"}</bdi>
                        </Td>
                      </Tr>
                      {open ? (
                        <tr className="bg-surface-2/60">
                          <td colSpan={7} className="border-b border-border px-4 py-3">
                            <div className="flex flex-wrap gap-4">
                              <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-caption">
                                <dt className="text-ink-2">{t("audit.entryId")}</dt>
                                <dd className="text-ink tabular" dir="ltr">
                                  {entry.id}
                                </dd>
                                <dt className="text-ink-2">{t("audit.ipAddress")}</dt>
                                <dd className="text-ink tabular" dir="ltr">
                                  {entry.ip_address ?? "—"}
                                </dd>
                                <dt className="text-ink-2">{t("audit.caseId")}</dt>
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
            label={t("audit.entriesUnit")}
          />
        </div>
      )}
    </div>
  );
}
