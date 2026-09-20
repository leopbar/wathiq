import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Hand, Inbox } from "lucide-react";
import { apiFetch, buildQuery } from "@/lib/api";
import { qk } from "@/lib/query";
import type { Page, ReviewTask, SlaState } from "@/lib/types";
import { PAGE_SIZE, SLA_LABEL, SLA_STATES } from "@/lib/constants";
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

const STATUS_OPTIONS = [
  { value: "all", label: "Any status" },
  { value: "pending", label: "Pending" },
  { value: "in_progress", label: "In progress" },
  { value: "completed", label: "Completed" },
];

export default function Review() {
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
      toast.success("Task claimed", { description: `${task.case_reference} is yours.` });
      void queryClient.invalidateQueries({ queryKey: ["review"] });
      navigate(`/review/${task.id}`);
    },
    onError: (error) =>
      toast.error("Could not claim the task", { description: describeError(error).message }),
  });

  const columns: Column<ReviewTask>[] = [
    {
      key: "reference",
      header: "Case",
      cell: (row) => (
        <div className="min-w-0">
          <p className="truncate font-medium text-ink tabular">{row.case_reference}</p>
          <p className="truncate text-caption text-ink-2">{row.customer_name}</p>
        </div>
      ),
      hideOnCard: true,
    },
    {
      key: "reason",
      header: "Reason",
      cell: (row) => (
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone={row.reason === "mandatory" ? "danger" : "warning"}>{row.reason_label}</Badge>
          <code className="text-caption text-ink-2/80">{row.reason_code}</code>
        </div>
      ),
    },
    {
      key: "volume",
      header: "Scope",
      cell: (row) => (
        <span className="text-small text-ink-2 tabular">
          {row.field_count} fields · {row.open_finding_count} findings
        </span>
      ),
    },
    {
      key: "assignee",
      header: "Assignee",
      cell: (row) =>
        row.assigned_to ? (
          <span className="text-small text-ink">
            {row.assigned_to.id === user?.id ? "You" : row.assigned_to.full_name}
          </span>
        ) : (
          <span className="text-small text-ink-2">Unclaimed</span>
        ),
    },
    {
      key: "sla",
      header: "SLA",
      cell: (row) => <SlaTimer dueAt={row.sla_due_at} state={row.sla_state} />,
      hideOnCard: true,
    },
    {
      key: "created",
      header: "Waiting",
      cell: (row) => <span className="text-small text-ink-2">{formatRelative(row.created_at)}</span>,
    },
    {
      key: "action",
      header: "Action",
      cell: (row) =>
        row.status === "completed" ? (
          <Badge tone="success">{row.decision ?? "done"}</Badge>
        ) : row.assigned_to && row.assigned_to.id !== user?.id ? (
          <Badge tone="neutral">Claimed</Badge>
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
            {row.assigned_to?.id === user?.id ? "Continue" : "Claim"}
          </Button>
        ),
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        title="Review queue"
        description="Only the cases the system is genuinely unsure about reach this list. Claim a task to work it end to end."
      />

      <Card className="flex flex-wrap items-center gap-4 p-4">
        <Switch id="review-mine" checked={mine} onCheckedChange={(v) => { setMine(v); setPage(1); }} label="Only mine" />
        <Select
          value={status}
          onValueChange={(value) => {
            setStatus(value);
            setPage(1);
          }}
          ariaLabel="Filter by task status"
          className="w-full sm:w-44"
          options={STATUS_OPTIONS}
        />
        <Select
          value={slaState}
          onValueChange={(value) => {
            setSlaState(value);
            setPage(1);
          }}
          ariaLabel="Filter by SLA state"
          className="w-full sm:w-44"
          options={[
            { value: "all", label: "Any SLA state" },
            ...SLA_STATES.map((s: SlaState) => ({ value: s, label: SLA_LABEL[s] })),
          ]}
        />
      </Card>

      <DataTable
        caption="Review queue"
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
            <span className="font-medium text-ink tabular">{row.case_reference}</span>
            <SlaTimer dueAt={row.sla_due_at} state={row.sla_state} />
          </div>
        )}
        empty={
          <EmptyState
            icon={Inbox}
            title="Nothing waiting"
            description={
              mine
                ? "You have no tasks assigned. Switch off “Only mine” to see the whole queue."
                : "The queue is empty — everything the pipeline produced was confident enough to pass straight through."
            }
            action={
              mine ? (
                <Button size="sm" variant="secondary" onClick={() => setMine(false)}>
                  Show the whole queue
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
              label="tasks"
            />
          ) : null
        }
      />
    </div>
  );
}
