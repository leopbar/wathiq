import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
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
            {t("roleSummary.openQueue")}
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
          title={t("roleSummary.queueClear")}
          description={t("roleSummary.queueClearDescription")}
          action={
            <Link to="/cases" className={buttonVariants({ variant: "secondary", size: "sm" })}>
              {t("roleSummary.browseCases")}
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
                    <bdi>{task.case_reference}</bdi>
                    <span className="ms-2 font-normal text-ink-2">{task.customer_name}</span>
                  </p>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <Badge tone={task.reason === "mandatory" ? "danger" : "warning"}>
                      {task.reason_label}
                    </Badge>
                    <span className="text-caption text-ink-2">
                      {t("roleSummary.taskCounts", {
                        fields: task.field_count,
                        count: task.open_finding_count,
                      })}
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
  const { t } = useTranslation();
  if (role === "reviewer") {
    return (
      <QueueSummary
        mine
        title={t("roleSummary.yourQueue")}
        description={t("roleSummary.yourQueueDescription")}
      />
    );
  }

  if (role === "supervisor" || role === "admin") {
    return (
      <QueueSummary
        mine={false}
        title={t("roleSummary.teamQueue")}
        description={t("roleSummary.teamQueueDescription")}
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
          <p className="text-body font-medium text-ink">{t("roleSummary.auditorTitle")}</p>
          <p className="mt-1 max-w-2xl text-small text-ink-2">
            {t("roleSummary.auditorBody")}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link to="/audit" className={buttonVariants({ variant: "secondary", size: "sm" })}>
              <ShieldCheck className="h-3.5 w-3.5" aria-hidden />
              {t("roleSummary.openAudit")}
            </Link>
            <Link to="/quality" className={buttonVariants({ variant: "ghost", size: "sm" })}>
              {t("roleSummary.qualityEvidence")}
            </Link>
          </div>
        </div>
      </Card>
    );
  }

  return null;
}
