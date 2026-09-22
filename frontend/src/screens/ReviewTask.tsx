import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { qk } from "@/lib/query";
import type {
  ExtractedField,
  ReasonCode,
  ReviewDecision,
  ReviewDecisionPayload,
  ReviewTaskDetail,
} from "@/lib/types";
import { useAuth } from "@/auth/useAuth";
import { isReadOnly } from "@/auth/roles";
import { describeError, ErrorState } from "@/components/ErrorState";
import { DetailSkeleton } from "@/components/Skeletons";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Tabs } from "@/components/ui/tabs";
import { SlaTimer } from "@/components/SlaTimer";
import { StatusPill } from "@/components/StatusPill";
import { DocumentViewer } from "./case/DocumentViewer";
import { FindingsPanel } from "./case/FindingsPanel";
import { CorrectionList } from "./review/CorrectionList";
import { DecisionBar } from "./review/DecisionBar";
import { ShortcutHelp } from "./review/ShortcutHelp";

export default function ReviewTask() {
  const { t } = useTranslation();
  const { taskId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { role } = useAuth();
  const readOnly = isReadOnly(role);

  const [selectedField, setSelectedField] = useState<ExtractedField | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [decision, setDecision] = useState<ReviewDecision | null>(null);
  const [reasonCode, setReasonCode] = useState("");
  const [note, setNote] = useState("");
  const [helpOpen, setHelpOpen] = useState(false);

  const query = useQuery({
    queryKey: qk.reviewTask(taskId),
    queryFn: () => apiFetch<ReviewTaskDetail>(`/review/tasks/${taskId}`),
    enabled: Boolean(taskId),
  });

  const reasonCodes = useQuery({
    queryKey: qk.reasonCodes,
    queryFn: () => apiFetch<ReasonCode[]>("/review/reason-codes"),
    staleTime: 10 * 60_000,
  });

  const taskData = query.data;
  const fields = useMemo(() => taskData?.case.fields ?? [], [taskData]);

  const corrections = useMemo(
    () =>
      Object.entries(drafts)
        .filter(([fieldId, value]) => {
          const field = fields.find((f) => f.id === fieldId);
          if (!field) return false;
          return value !== (field.corrected_value ?? field.value ?? "");
        })
        .map(([field_id, value]) => ({ field_id, value })),
    [drafts, fields],
  );

  const submit = useMutation({
    mutationFn: (payload: ReviewDecisionPayload) =>
      apiFetch(`/review/tasks/${taskId}/decision`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      toast.success(t("reviewTask.recorded"), {
        description: t("reviewTask.recordedDescription"),
      });
      void queryClient.invalidateQueries({ queryKey: ["review"] });
      void queryClient.invalidateQueries({ queryKey: ["cases"] });
      navigate("/review");
    },
    onError: (error) =>
      toast.error(t("reviewTask.notSaved"), { description: describeError(error).message }),
  });

  const sendDecision = useCallback(() => {
    if (!decision) return;
    submit.mutate({
      decision,
      reason_code: reasonCode || undefined,
      note: note || undefined,
      field_corrections: corrections.length > 0 ? corrections : undefined,
    });
  }, [decision, reasonCode, note, corrections, submit]);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;

      const key = event.key.toLowerCase();
      if (key === "?") {
        event.preventDefault();
        setHelpOpen(true);
      } else if (readOnly) {
        return;
      } else if (key === "a") {
        setDecision("approve");
      } else if (key === "c") {
        setDecision("correct");
      } else if (key === "r") {
        setDecision("reject");
      } else if (key === "e") {
        setDecision("escalate");
      } else if (key === "j" || key === "k") {
        const index = fields.findIndex((f) => f.id === selectedField?.id);
        const next = key === "j" ? index + 1 : index - 1;
        if (next >= 0 && next < fields.length) setSelectedField(fields[next]);
        else if (index === -1 && fields.length > 0) setSelectedField(fields[0]);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [fields, selectedField, readOnly]);

  if (query.isPending) return <DetailSkeleton />;

  if (query.isError) {
    return (
      <Card>
        <ErrorState
          error={query.error}
          onRetry={() => void query.refetch()}
          title={t("reviewTask.loadError")}
        />
      </Card>
    );
  }

  const { task, case: caseDetail } = query.data;
  const activeDocument =
    caseDetail.documents.find((d) => d.id === selectedField?.document_id) ??
    caseDetail.documents[0] ??
    null;
  const completed = task.status === "completed";

  return (
    <div className="space-y-4 pb-2">
      <PageHeader
        breadcrumb={
          <Link
            to="/review"
            className="inline-flex items-center gap-1 text-small text-ink-2 hover:text-ink"
          >
            <ArrowLeft className="h-3.5 w-3.5 rtl:rotate-180" aria-hidden />
            {t("nav.review")}
          </Link>
        }
        title={
          <span className="flex flex-wrap items-center gap-3">
            <bdi className="tabular">{task.case_reference}</bdi>
            <StatusPill status={caseDetail.status} />
          </span>
        }
        description={
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="text-ink">{task.customer_name}</span>
            <Badge tone={task.reason === "mandatory" ? "danger" : "warning"}>
              {task.reason_label}
            </Badge>
            <SlaTimer dueAt={task.sla_due_at} state={task.sla_state} />
          </span>
        }
        actions={
          <Link
            to={`/cases/${caseDetail.id}`}
            className={buttonVariants({ variant: "secondary", size: "sm" })}
          >
            <ExternalLink className="h-3.5 w-3.5 rtl:-scale-x-100" aria-hidden />
            {t("reviewTask.fullCase")}
          </Link>
        }
      />

      {completed ? (
        <Card className="border-success/40 bg-success-soft/40 px-4 py-3">
          <p className="text-small text-ink">
            {t("reviewTask.completed")}
            {task.decision
              ? ` — ${t("reviewTask.decisionWas", { decision: t(`review.decisionValue.${task.decision}`) })}`
              : ""}
            {task.decision_reason_code ? (
              <>
                {" ("}
                <bdi>{task.decision_reason_code}</bdi>
                {")"}
              </>
            ) : null}
            .
          </p>
        </Card>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="flex min-h-[34rem] flex-col overflow-hidden">
          <DocumentViewer
            document={activeDocument}
            highlighted={selectedField}
            className="flex min-h-0 flex-1 flex-col"
          />
        </Card>

        <Card className="flex min-h-[34rem] flex-col overflow-hidden">
          <CardHeader
            title={t("reviewTask.fieldsAndFindings")}
            description={t("reviewTask.fieldsAndFindingsDescription")}
          />
          <Tabs
            className="min-h-0 flex-1"
            items={[
              {
                value: "fields",
                label: t("caseDetail.tabs.fields"),
                badge: <Badge tone="neutral">{fields.length}</Badge>,
                content: (
                  <div className="h-full overflow-y-auto scroll-thin">
                    <CorrectionList
                      fields={fields}
                      drafts={drafts}
                      disabled={readOnly || completed || submit.isPending}
                      selectedFieldId={selectedField?.id ?? null}
                      onSelectField={setSelectedField}
                      onDraftChange={(fieldId, value) =>
                        setDrafts((prev) => {
                          const next = { ...prev };
                          if (value === undefined) delete next[fieldId];
                          else next[fieldId] = value;
                          return next;
                        })
                      }
                    />
                  </div>
                ),
              },
              {
                value: "findings",
                label: t("caseDetail.tabs.findings"),
                badge:
                  caseDetail.open_finding_count > 0 ? (
                    <Badge tone="warning">{caseDetail.open_finding_count}</Badge>
                  ) : undefined,
                content: (
                  <div className="h-full overflow-y-auto scroll-thin">
                    <FindingsPanel findings={caseDetail.findings} />
                  </div>
                ),
              },
            ]}
          />
          <DecisionBar
            decision={decision}
            onDecisionChange={setDecision}
            reasonCodes={reasonCodes.data ?? []}
            reasonCode={reasonCode}
            onReasonCodeChange={setReasonCode}
            note={note}
            onNoteChange={setNote}
            onSubmit={sendDecision}
            submitting={submit.isPending}
            disabled={readOnly || completed}
            correctionCount={corrections.length}
            onOpenHelp={() => setHelpOpen(true)}
          />
        </Card>
      </div>

      <ShortcutHelp open={helpOpen} onOpenChange={setHelpOpen} />
    </div>
  );
}
