import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { ArrowUpFromLine, Hand, Inbox } from "lucide-react";
import { apiFetch, buildQuery } from "@/lib/api";
import { qk } from "@/lib/query";
import type { Page, ReviewTask, SlaState } from "@/lib/types";
import { PAGE_SIZE, SLA_STATES } from "@/lib/constants";
import { formatRelative } from "@/lib/format";
import { useAuth } from "@/auth/useAuth";
import { describeError } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { DataTable, type Column } from "@/components/DataTable";
import { EmptyState } from "@/components/EmptyState";
import { SlaTimer } from "@/components/SlaTimer";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/toggle";
import { Pagination } from "@/components/ui/pagination";

export default function Review() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const [mine, setMine] = useState(false);
  const [status, setStatus] = useState("pending");
  const [slaState, setSlaState] = useState("all");
  const [page, setPage] = useState(1);

  const params = useMemo(
    () => ({
      mine: mine ? true : undefined,
      status: status === "all" ? "" : status,
      sla_state: slaState === "all" ? "" : slaState,
      page,
      size: PAGE_SIZE,
    }),
    [mine, status, slaState, page],
  );

  const query = useQuery({
    queryKey: qk.reviewQueue(params),
    queryFn: () => apiFetch<Page<ReviewTask>>(`/review/queue${buildQuery(params)}`),
    placeholderData: keepPreviousData,
  });

  const claim = useMutation({
    mutationFn: (taskId: string) =>
      apiFetch<ReviewTask>(`/review/tasks/${taskId}/claim`, { method: "POST" }),
    onSuccess: (task) => {
      toast.success(t("review.claimed"), {
        description: t("review.claimedDescription", { reference: task.case_reference }),
      });
      void queryClient.invalidateQueries({ queryKey: ["review"] });
      navigate(`/review/${task.id}`);
    },
    onError: (error) =>
      toast.error(t("review.claimError"), { description: describeError(error).message }),
  });

  const columns: Column<ReviewTask>[] = [
    {
      key: "reference",
      header: t("review.columns.case"),
      cell: (row) => (
        <div className="min-w-0">
          <p className="truncate font-medium text-ink tabular">
            <bdi>{row.case_reference}</bdi>
          </p>
          <p className="truncate text-caption text-ink-2">{row.customer_name}</p>
        </div>
      ),
      hideOnCard: true,
    },
    {
      key: "reason",
      header: t("review.columns.reason"),
      cell: (row) => (
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone={row.reason === "mandatory" ? "danger" : "warning"}>{row.reason_label}</Badge>
          <code className="text-caption text-ink-2/80" dir="ltr">
            {row.reason_code}
          </code>
          {/* The SLA timer already found this one late and moved it to the supervisor queue.
              Worth saying on the row: it explains why a reviewer no longer sees it. */}
          {row.escalated_at ? (
            <Badge tone="warning">
              <ArrowUpFromLine className="h-3 w-3" aria-hidden />
              {t("review.escalated")}
            </Badge>
          ) : null}
        </div>
      ),
    },
    {
      key: "volume",
      header: t("review.columns.scope"),
      cell: (row) => (
        <span className="text-small text-ink-2 tabular">
          {t("review.scope", { fields: row.field_count, findings: row.open_finding_count })}
        </span>
      ),
    },
    {
      key: "assignee",
      header: t("review.columns.assignee"),
      cell: (row) =>
        row.assigned_to ? (
          <span className="text-small text-ink">
            {row.assigned_to.id === user?.id ? t("review.you") : row.assigned_to.full_name}
          </span>
        ) : (
          <span className="text-small text-ink-2">{t("review.unclaimed")}</span>
        ),
    },
    {
      key: "sla",
      header: t("review.columns.sla"),
      cell: (row) => <SlaTimer dueAt={row.sla_due_at} state={row.sla_state} />,
      hideOnCard: true,
    },
    {
      key: "created",
      header: t("review.columns.waiting"),
      cell: (row) => <span className="text-small text-ink-2">{formatRelative(row.created_at)}</span>,
    },
    {
      key: "action",
      header: t("review.columns.action"),
      cell: (row) =>
        row.status === "completed" ? (
          <Badge tone="success">
            {row.decision ? t(`review.decisionValue.${row.decision}`) : t("review.done")}
          </Badge>
        ) : row.assigned_to && row.assigned_to.id !== user?.id ? (
          <Badge tone="neutral">{t("review.claimedBadge")}</Badge>
        ) : (
          <Button
            size="sm"
            variant={row.assigned_to ? "secondary" : "primary"}
            loading={claim.isPending && claim.variables === row.id}
            onClick={(event) => {
              event.stopPropagation();
              if (row.assigned_to?.id === user?.id) navigate(`/review/${row.id}`);
              else claim.mutate(row.id);
            }}
          >
            <Hand className="h-3.5 w-3.5" aria-hidden />
            {row.assigned_to?.id === user?.id ? t("review.continue") : t("review.claim")}
          </Button>
        ),
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        title={t("nav.review")}
        description={t("review.description")}
      />

      <Card className="flex flex-wrap items-center gap-4 p-4">
        <Switch
          id="review-mine"
          checked={mine}
          onCheckedChange={(v) => {
            setMine(v);
            setPage(1);
          }}
          label={t("review.onlyMine")}
        />
        <Select
          value={status}
          onValueChange={(value) => {
            setStatus(value);
            setPage(1);
          }}
          ariaLabel={t("review.statusFilter")}
          className="w-full sm:w-44"
          options={[
            { value: "all", label: t("review.status.all") },
            { value: "pending", label: t("review.status.pending") },
            { value: "in_progress", label: t("review.status.in_progress") },
            { value: "completed", label: t("review.status.completed") },
          ]}
        />
        <Select
          value={slaState}
          onValueChange={(value) => {
            setSlaState(value);
            setPage(1);
          }}
          ariaLabel={t("cases.slaFilter")}
          className="w-full sm:w-44"
          options={[
            { value: "all", label: t("cases.anySla") },
            ...SLA_STATES.map((s: SlaState) => ({ value: s, label: t(`catalog.sla.${s}`) })),
          ]}
        />
      </Card>

      <DataTable
        caption={t("nav.review")}
        columns={columns}
        rows={query.data?.items ?? []}
        rowKey={(row) => row.id}
        isPending={query.isPending}
        isError={query.isError}
        error={query.error}
        onRetry={() => void query.refetch()}
        onRowClick={(row) => navigate(`/review/${row.id}`)}
        cardTitle={(row) => (
          <div className="flex items-center justify-between gap-2">
            <bdi className="font-medium text-ink tabular">{row.case_reference}</bdi>
            <SlaTimer dueAt={row.sla_due_at} state={row.sla_state} />
          </div>
        )}
        empty={
          <EmptyState
            icon={Inbox}
            title={t("review.emptyTitle")}
            description={
              mine
                ? t("review.emptyMine")
                : t("review.emptyAll")
            }
            action={
              mine ? (
                <Button size="sm" variant="secondary" onClick={() => setMine(false)}>
                  {t("review.showAll")}
                </Button>
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
              label={t("review.tasksUnit")}
            />
          ) : null
        }
      />
    </div>
  );
}
