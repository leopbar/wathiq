import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { FilePlus2, FileStack } from "lucide-react";
import { apiFetch, buildQuery } from "@/lib/api";
import { qk } from "@/lib/query";
import type { CaseStatus, CaseSummary, Page, SlaState } from "@/lib/types";
import {
  CASE_STATUSES,
  CASE_STATUS_LABEL,
  CASE_TYPES,
  CASE_TYPE_LABEL,
  PAGE_SIZE,
  SLA_LABEL,
  SLA_STATES,
} from "@/lib/constants";
import { formatNumber, formatRelative } from "@/lib/format";
import { useAuth } from "@/auth/useAuth";
import { can } from "@/auth/roles";
import { useDebounced } from "@/lib/useDebounced";
import { PageHeader } from "@/components/PageHeader";
import { DataTable, type Column } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { FilterChips } from "@/components/FilterChips";
import { StatusPill } from "@/components/StatusPill";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { SlaTimer } from "@/components/SlaTimer";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { SearchInput } from "@/components/ui/search-input";
import { Checkbox } from "@/components/ui/toggle";
import { Pagination } from "@/components/ui/pagination";

export default function Cases() {
  const navigate = useNavigate();
  const { role } = useAuth();

  const [search, setSearch] = useState("");
  const [statuses, setStatuses] = useState<CaseStatus[]>([]);
  const [slaState, setSlaState] = useState<string>("all");
  const [caseType, setCaseType] = useState<string>("all");
  const [mine, setMine] = useState(false);
  const [sort, setSort] = useState("-created_at");
  const [page, setPage] = useState(1);

  const q = useDebounced(search, 300);

  const params = useMemo(
    () => ({
      q,
      status: statuses,
      sla_state: slaState === "all" ? "" : slaState,
      case_type: caseType === "all" ? "" : caseType,
      assigned_to_me: mine ? true : undefined,
      sort,
      page,
      size: PAGE_SIZE,
    }),
    [q, statuses, slaState, caseType, mine, sort, page],
  );

  const query = useQuery({
    queryKey: qk.cases(params),
    queryFn: () => apiFetch<Page<CaseSummary>>(`/cases${buildQuery(params)}`),
    placeholderData: keepPreviousData,
  });

  const toggleStatus = (value: CaseStatus) => {
    setPage(1);
    setStatuses((prev) =>
      prev.includes(value) ? prev.filter((s) => s !== value) : [...prev, value],
    );
  };

  const hasFilters =
    Boolean(q) || statuses.length > 0 || slaState !== "all" || caseType !== "all" || mine;

  const columns: Column<CaseSummary>[] = [
    {
      key: "reference",
      header: "Reference",
      sortField: "reference",
      cell: (row) => <span className="font-medium text-ink tabular">{row.reference}</span>,
      hideOnCard: true,
    },
    {
      key: "customer",
      header: "Customer",
      sortField: "customer_name",
      cell: (row) => (
        <div className="min-w-0">
          <p className="truncate text-body text-ink">{row.customer_name}</p>
          <p className="truncate text-caption text-ink-2" dir="rtl">
            {row.customer_name_ar}
          </p>
        </div>
      ),
      className: "max-w-56",
    },
    {
      key: "case_type",
      header: "Type",
      cell: (row) => <span className="text-small text-ink-2">{CASE_TYPE_LABEL[row.case_type]}</span>,
    },
    {
      key: "status",
      header: "Status",
      cell: (row) => <StatusPill status={row.status} />,
      hideOnCard: true,
    },
    {
      key: "confidence",
      header: "Confidence",
      sortField: "confidence",
      cell: (row) => <ConfidenceBadge value={row.confidence} showLabel={false} />,
    },
    {
      key: "documents",
      header: "Docs",
      cell: (row) => <span className="tabular text-small">{formatNumber(row.document_count)}</span>,
    },
    {
      key: "findings",
      header: "Findings",
      cell: (row) =>
        row.open_finding_count > 0 ? (
          <Badge tone="warning">{formatNumber(row.open_finding_count)} open</Badge>
        ) : (
          <span className="text-small text-ink-2 tabular">{formatNumber(row.finding_count)}</span>
        ),
    },
    {
      key: "sla",
      header: "SLA",
      cell: (row) => <SlaTimer dueAt={row.sla_due_at} state={row.sla_state} />,
    },
    {
      key: "updated",
      header: "Updated",
      sortField: "updated_at",
      cell: (row) => <span className="text-small text-ink-2">{formatRelative(row.updated_at)}</span>,
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Cases"
        description="Every document package in the pipeline, with its status, confidence and SLA."
        actions={
          can(role, "case.create") ? (
            <Link to="/cases/new" className={buttonVariants({ variant: "primary", size: "sm" })}>
              <FilePlus2 className="h-3.5 w-3.5" aria-hidden />
              New case
            </Link>
          ) : null
        }
      />

      <Card className="space-y-3 p-4">
        <div className="flex flex-wrap items-center gap-3">
          <SearchInput
            value={search}
            onChange={(value) => {
              setSearch(value);
              setPage(1);
            }}
            placeholder="Search reference or customer…"
            ariaLabel="Search cases"
            className="w-full sm:max-w-xs"
          />
          <Select
            value={caseType}
            onValueChange={(value) => {
              setCaseType(value);
              setPage(1);
            }}
            ariaLabel="Filter by case type"
            className="w-full sm:w-56"
            placeholder="All case types"
            options={[
              { value: "all", label: "All case types" },
              ...CASE_TYPES.map((t) => ({ value: t, label: CASE_TYPE_LABEL[t] })),
            ]}
          />
          <Select
            value={slaState}
            onValueChange={(value) => {
              setSlaState(value);
              setPage(1);
            }}
            ariaLabel="Filter by SLA state"
            className="w-full sm:w-44"
            placeholder="Any SLA state"
            options={[
              { value: "all", label: "Any SLA state" },
              ...SLA_STATES.map((s: SlaState) => ({ value: s, label: SLA_LABEL[s] })),
            ]}
          />
          <Checkbox
            id="cases-mine"
            checked={mine}
            onCheckedChange={(value) => {
              setMine(value);
              setPage(1);
            }}
            label="Assigned to me"
          />
        </div>

        <FilterChips
          legend="Filter by status"
          options={CASE_STATUSES.map((s) => ({ value: s, label: CASE_STATUS_LABEL[s] }))}
          selected={statuses}
          onToggle={toggleStatus}
        />
      </Card>

      <DataTable
        caption="Cases"
        columns={columns}
        rows={query.data?.items ?? []}
        rowKey={(row) => row.id}
        isPending={query.isPending}
        isError={query.isError}
        error={query.error}
        onRetry={() => void query.refetch()}
        onRowClick={(row) => navigate(`/cases/${row.id}`)}
        sort={sort}
        onSortChange={(next) => {
          setSort(next);
          setPage(1);
        }}
        cardTitle={(row) => (
          <div className="flex items-center justify-between gap-2">
            <span className="font-medium text-ink tabular">{row.reference}</span>
            <StatusPill status={row.status} />
          </div>
        )}
        empty={
          <EmptyState
            icon={FileStack}
            title={hasFilters ? "No cases match these filters" : "No cases yet"}
            description={
              hasFilters
                ? "Try widening the search or clearing a status chip."
                : "Create the first case to see the pipeline in action."
            }
            action={
              hasFilters ? (
                <button
                  type="button"
                  className={buttonVariants({ variant: "secondary", size: "sm" })}
                  onClick={() => {
                    setSearch("");
                    setStatuses([]);
                    setSlaState("all");
                    setCaseType("all");
                    setMine(false);
                    setPage(1);
                  }}
                >
                  Clear filters
                </button>
              ) : can(role, "case.create") ? (
                <Link
                  to="/cases/new"
                  className={buttonVariants({ variant: "primary", size: "sm" })}
                >
                  Create a case
                </Link>
              ) : null
            }
          />
        }
        footer={
          query.data && query.data.total > 0 ? (
            <Pagination
              page={query.data.page}
              pages={query.data.pages}
              total={query.data.total}
              size={query.data.size}
              onPageChange={setPage}
              label="cases"
            />
          ) : null
        }
      />
    </div>
  );
}
