import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Eye, ShieldCheck } from "lucide-react";
import { apiFetch, buildQuery } from "@/lib/api";
import { qk } from "@/lib/query";
import type { Page, ReviewTask, Role } from "@/lib/types";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { ListSkeleton } from "@/components/Skeletons";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { SlaTimer } from "@/components/SlaTimer";

function QueueSummary({
  mine,
  title,
  description,
}: {
  mine: boolean;
  title: string;
  description: string;
}) {
  // No status filter: the endpoint already excludes completed work. Asking for `pending` as well
  // would hide everything, because a task assigned to you is `in_progress`, never `pending`.
  const params = { mine, size: 5, page: 1 };
  const query = useQuery({
    queryKey: qk.reviewQueue(params),
    queryFn: () => apiFetch<Page<ReviewTask>>(`/review/queue${buildQuery(params)}`),
  });

  return (
    <Card>
      <CardHeader
        title={title}
        description={description}
        action={
          <Link to="/review" className={buttonVariants({ variant: "secondary", size: "sm" })}>
            Open queue
            <ArrowRight className="h-3.5 w-3.5 rtl:rotate-180" aria-hidden />
          </Link>
        }
      />
      {query.isPending ? (
        <ListSkeleton rows={4} />
      ) : query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : query.data.items.length === 0 ? (
        <EmptyState
          title="Queue is clear"
          description="No pending review tasks are waiting for you right now."
          action={
            <Link to="/cases" className={buttonVariants({ variant: "secondary", size: "sm" })}>
              Browse cases
            </Link>
          }
        />
      ) : (
        <ul className="divide-y divide-border">
          {query.data.items.map((task) => (
            <li key={task.id}>
              <Link
                to={`/review/${task.id}`}
                className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-surface-2/70"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-body font-medium text-ink">
                    {task.case_reference}
                    <span className="ms-2 font-normal text-ink-2">{task.customer_name}</span>
                  </p>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <Badge tone={task.reason === "mandatory" ? "danger" : "warning"}>
                      {task.reason_label}
                    </Badge>
                    <span className="text-caption text-ink-2">
                      {task.field_count} fields · {task.open_finding_count} open{" "}
                      {task.open_finding_count === 1 ? "finding" : "findings"}
                    </span>
                  </div>
                </div>
                <SlaTimer dueAt={task.sla_due_at} state={task.sla_state} />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function RoleSummary({ role }: { role: Role | undefined }) {
  if (role === "reviewer") {
    return (
      <QueueSummary
        mine
        title="Your review queue"
        description="Tasks assigned to you, most urgent first."
      />
    );
  }

  if (role === "supervisor" || role === "admin") {
    return (
      <QueueSummary
        mine={false}
        title="Team review queue"
        description="Everything waiting across the team, with live SLA timers."
      />
    );
  }

  if (role === "auditor") {
    return (
      <Card className="flex items-start gap-3 p-5">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-info-soft text-info">
          <Eye className="h-4 w-4" aria-hidden />
        </span>
        <div>
          <p className="text-body font-medium text-ink">Read-only auditor view</p>
          <p className="mt-1 max-w-2xl text-small text-ink-2">
            You can open every case, field, finding and audit entry, including the prompt and model
            version behind each decision. Nothing on this account can change a case, and the API
            enforces that independently of this interface.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link to="/audit" className={buttonVariants({ variant: "secondary", size: "sm" })}>
              <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
              Open audit log
            </Link>
            <Link to="/quality" className={buttonVariants({ variant: "ghost", size: "sm" })}>
              Quality evidence
            </Link>
          </div>
        </div>
      </Card>
    );
  }

  return null;
}
