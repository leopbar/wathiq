import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ClipboardCheck, RefreshCw } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { qk } from "@/lib/query";
import type {
  CaseAssurance,
  CaseDetail as CaseDetailType,
  ExtractedField,
  ProcessStatus,
} from "@/lib/types";
import { CASE_TYPE_LABEL } from "@/lib/constants";
import { formatDateTime, formatDuration, formatUsd } from "@/lib/format";
import { useAuth } from "@/auth/useAuth";
import { can } from "@/auth/roles";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Tabs } from "@/components/ui/tabs";
import { CopyButton } from "@/components/ui/code-block";
import { DetailSkeleton } from "@/components/Skeletons";
import { ErrorState } from "@/components/ErrorState";
import { EmptyState } from "@/components/EmptyState";
import { StatusPill, PriorityPill, RiskPill } from "@/components/StatusPill";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { SlaTimer } from "@/components/SlaTimer";
import { Timeline } from "@/components/Timeline";
import { DocumentList } from "./case/DocumentList";
import { DocumentViewer } from "./case/DocumentViewer";
import { FieldsPanel } from "./case/FieldsPanel";
import { FindingsPanel } from "./case/FindingsPanel";
import { AssurancePanel } from "./case/AssurancePanel";
import { ProcessPanel } from "./case/ProcessPanel";

/**
 * The statuses a case can still move out of on its own.
 *
 * `approved` and `posting` are in the list because the business process continues after the
 * agent graph finishes: the case still has to be posted to core banking and sealed into the
 * audit trail. Leaving them out would stop the polling one step early and leave the screen
 * showing "Approved" until the user reloaded.
 */
const MOVING_STATUSES = new Set(["intake", "processing", "approved", "posting"]);

function MetaItem({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="label-caption text-ink-2">{label}</dt>
      <dd className="mt-0.5 text-small text-ink">{value}</dd>
    </div>
  );
}

export default function CaseDetail() {
  const { id = "" } = useParams();
  const { role } = useAuth();
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [selectedField, setSelectedField] = useState<ExtractedField | null>(null);

  const query = useQuery({
    queryKey: qk.caseDetail(id),
    queryFn: () => apiFetch<CaseDetailType>(`/cases/${id}`),
    enabled: Boolean(id),
    // A case opened while the pipeline is still running would otherwise sit on a stale
    // "Processing" until the user reloaded. Poll only while it is actually moving; once it
    // settles (or parks at the review gate) nothing changes without a user action, so the
    // polling stops and the page costs nothing.
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      return status && MOVING_STATUSES.has(status) ? 1_000 : false;
    },
  });

  const caseData = query.data;
  // While the pipeline is still moving, the checkpoint grows: guardrails, then workers, then
  // the critic, then the investigation. A single fetch on mount would freeze whatever
  // half-finished snapshot it happened to catch, so this follows the case the same way the
  // detail query does and stops as soon as the run settles.
  const caseIsMoving = Boolean(caseData && MOVING_STATUSES.has(caseData.status));

  // The evidence behind the case: guardrails, workers, critic, investigation, tool calls.
  // Read from the agent's checkpoint, so it only exists once the case has actually run.
  const assuranceQuery = useQuery({
    queryKey: qk.caseAssurance(id),
    queryFn: () => apiFetch<CaseAssurance>(`/cases/${id}/assurance`),
    enabled: Boolean(id),
    staleTime: 0,
    refetchInterval: caseIsMoving ? 1_000 : false,
  });

  // Where the case is in the business process. Built from the case's own event log, so it
  // follows the case for as long as the case is moving — and the process keeps moving after the
  // graph finishes, through posting and the audit seal.
  const processQuery = useQuery({
    queryKey: qk.caseProcess(id),
    queryFn: () => apiFetch<ProcessStatus>(`/cases/${id}/process`),
    enabled: Boolean(id),
    staleTime: 0,
    refetchInterval: caseIsMoving ? 1_000 : false,
  });

  // Polling stops the moment the case settles, and the last poll before that almost always
  // caught the checkpoint one node short — leaving the panel showing "0 steps" for a run that
  // did six. One refetch on every status change closes that gap.
  const caseStatus = caseData?.status;
  const refetchAssurance = assuranceQuery.refetch;
  const refetchProcess = processQuery.refetch;
  useEffect(() => {
    if (caseStatus) {
      void refetchAssurance();
      void refetchProcess();
    }
  }, [caseStatus, refetchAssurance, refetchProcess]);

  useEffect(() => {
    if (caseData && !selectedDocumentId && caseData.documents.length > 0) {
      setSelectedDocumentId(caseData.documents[0].id);
    }
  }, [caseData, selectedDocumentId]);

  const selectedDocument = useMemo(
    () => caseData?.documents.find((d) => d.id === selectedDocumentId) ?? null,
    [caseData, selectedDocumentId],
  );

  const openReviewTask = caseData?.review_tasks.find((t) => t.status !== "completed");

  if (query.isPending) return <DetailSkeleton />;

  if (query.isError) {
    return (
      <Card>
        <ErrorState
          error={query.error}
          onRetry={() => void query.refetch()}
          title="This case could not be loaded"
        />
      </Card>
    );
  }

  const detail = query.data;

  const highlightField = (field: ExtractedField) => {
    setSelectedField(field);
    if (field.document_id) setSelectedDocumentId(field.document_id);
  };

  return (
    <div className="space-y-4">
      <PageHeader
        breadcrumb={
          <Link
            to="/cases"
            className="inline-flex items-center gap-1 text-small text-ink-2 hover:text-ink"
          >
            <ArrowLeft className="h-3.5 w-3.5 rtl:rotate-180" aria-hidden />
            All cases
          </Link>
        }
        title={
          <span className="flex flex-wrap items-center gap-3">
            <span className="tabular">{detail.reference}</span>
            <StatusPill status={detail.status} />
            {detail.straight_through ? <Badge tone="success">Straight-through</Badge> : null}
          </span>
        }
        description={
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="text-ink">{detail.customer_name}</span>
            <span dir="rtl" className="text-ink-2">
              {detail.customer_name_ar}
            </span>
            <span className="text-ink-2">· {CASE_TYPE_LABEL[detail.case_type]}</span>
          </span>
        }
        actions={
          <>
            <Button variant="secondary" size="sm" onClick={() => void query.refetch()}>
              <RefreshCw className="h-3.5 w-3.5" aria-hidden />
              Refresh
            </Button>
            {openReviewTask && can(role, "review") ? (
              <Link
                to={`/review/${openReviewTask.id}`}
                className={buttonVariants({ variant: "primary", size: "sm" })}
              >
                <ClipboardCheck className="h-3.5 w-3.5" aria-hidden />
                Open review task
              </Link>
            ) : null}
          </>
        }
      />

      <Card className="p-4">
        <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-6">
          <MetaItem label="Confidence" value={<ConfidenceBadge value={detail.confidence} />} />
          <MetaItem label="Risk" value={<RiskPill risk={detail.risk_level} />} />
          <MetaItem label="Priority" value={<PriorityPill priority={detail.priority} />} />
          <MetaItem
            label="SLA"
            value={<SlaTimer dueAt={detail.sla_due_at} state={detail.sla_state} />}
          />
          <MetaItem label="Processing" value={formatDuration(detail.processing_ms)} />
          <MetaItem label="Cost" value={formatUsd(detail.cost_usd)} />
          <MetaItem label="Created" value={formatDateTime(detail.created_at)} />
          <MetaItem label="Updated" value={formatDateTime(detail.updated_at)} />
          <MetaItem label="Created by" value={detail.created_by?.full_name ?? "—"} />
          <MetaItem label="Assigned to" value={detail.assigned_to?.full_name ?? "Unassigned"} />
          <MetaItem
            label="Documents"
            value={`${detail.documents.length} file${detail.documents.length === 1 ? "" : "s"}`}
          />
          <MetaItem
            label="Findings"
            value={`${detail.open_finding_count} open / ${detail.finding_count}`}
          />
        </dl>

        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-3">
          <Badge tone="primary">Conductor workflow / LangGraph thread</Badge>
          <code className="truncate text-caption text-ink tabular" dir="ltr">
            {detail.thread_id}
          </code>
          <CopyButton value={detail.thread_id} label="Copy thread id" />
          <span className="text-caption text-ink-2">
            One identifier links the process layer, the agent graph and the audit trail.
          </span>
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,15rem)_minmax(0,1fr)_minmax(0,24rem)]">
        <Card className="h-fit overflow-hidden">
          <CardHeader title="Documents" />
          <DocumentList
            documents={detail.documents}
            selectedId={selectedDocumentId}
            onSelect={(docId) => {
              setSelectedDocumentId(docId);
              setSelectedField(null);
            }}
          />
        </Card>

        <Card className="flex min-h-[32rem] flex-col overflow-hidden">
          <DocumentViewer
            document={selectedDocument}
            highlighted={
              selectedField && selectedField.document_id === selectedDocumentId
                ? selectedField
                : null
            }
            className="flex min-h-0 flex-1 flex-col"
          />
        </Card>

        <Card className="flex max-h-[46rem] min-h-[32rem] flex-col overflow-hidden">
          <Tabs
            className="min-h-0 flex-1"
            items={[
              {
                value: "fields",
                label: "Fields",
                badge: <Badge tone="neutral">{detail.fields.length}</Badge>,
                content: (
                  <div className="h-full overflow-y-auto scroll-thin">
                    <FieldsPanel
                      fields={detail.fields}
                      documents={detail.documents}
                      selectedFieldId={selectedField?.id ?? null}
                      onSelectField={highlightField}
                    />
                  </div>
                ),
              },
              {
                value: "findings",
                label: "Findings",
                badge:
                  detail.open_finding_count > 0 ? (
                    <Badge tone="warning">{detail.open_finding_count}</Badge>
                  ) : (
                    <Badge tone="neutral">{detail.finding_count}</Badge>
                  ),
                content: (
                  <div className="h-full overflow-y-auto scroll-thin">
                    <FindingsPanel findings={detail.findings} />
                  </div>
                ),
              },
              {
                value: "process",
                label: "Process",
                badge: processQuery.data ? (
                  processQuery.data.finished ? (
                    <Badge tone="success">finished</Badge>
                  ) : (
                    <Badge tone="neutral">
                      {processQuery.data.steps.filter((step) => step.status === "completed").length}
                      /{processQuery.data.steps.length}
                    </Badge>
                  )
                ) : undefined,
                content: (
                  <div className="h-full overflow-y-auto scroll-thin">
                    {processQuery.data ? (
                      <ProcessPanel status={processQuery.data} />
                    ) : (
                      <EmptyState
                        title={processQuery.isPending ? "Loading…" : "The process view is unavailable"}
                        description={
                          processQuery.isPending
                            ? "Reading this case's process record."
                            : "The process layer could not be asked about this case."
                        }
                      />
                    )}
                  </div>
                ),
              },
              {
                value: "assurance",
                label: "Assurance",
                badge:
                  assuranceQuery.data?.available === false ? (
                    <Badge tone="outline">seeded</Badge>
                  ) : assuranceQuery.data ? (
                    <Badge tone="neutral">{assuranceQuery.data.tool_calls.length} tools</Badge>
                  ) : undefined,
                content: (
                  <div className="h-full overflow-y-auto scroll-thin">
                    {assuranceQuery.data ? (
                      <AssurancePanel assurance={assuranceQuery.data} />
                    ) : (
                      <EmptyState
                        title={assuranceQuery.isPending ? "Loading…" : "No evidence available"}
                        description={
                          assuranceQuery.isPending
                            ? "Reading the agent's checkpoint."
                            : "The agent checkpoint for this case could not be read."
                        }
                      />
                    )}
                  </div>
                ),
              },
              {
                value: "timeline",
                label: "Timeline",
                badge: <Badge tone="neutral">{detail.timeline.length}</Badge>,
                content: (
                  <div className="h-full overflow-y-auto scroll-thin p-4">
                    {detail.timeline.length === 0 ? (
                      <EmptyState
                        title="No events yet"
                        description="The agent timeline fills in as the pipeline runs."
                      />
                    ) : (
                      <Timeline events={detail.timeline} />
                    )}
                  </div>
                ),
              },
            ]}
          />
        </Card>
      </div>
    </div>
  );
}
