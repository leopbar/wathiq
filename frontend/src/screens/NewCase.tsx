import { useState, type FormEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { toast } from "sonner";
import { Rocket } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { CaseDetail, StartCaseResponse } from "@/lib/types";
import {
  CASE_TYPES,
  CASE_TYPE_LABEL,
  PIPELINE_NODES,
  PRIORITIES,
  PRIORITY_LABEL,
} from "@/lib/constants";
import { describeError } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Dropzone, type PickedFile } from "./newcase/Dropzone";
import { PipelineProgress } from "./newcase/PipelineProgress";

const schema = z.object({
  customer_name: z.string().trim().min(2, "Customer name is required"),
  customer_name_ar: z.string().trim().optional(),
  case_type: z.enum(["kyc_refresh", "salary_certificate"]),
  priority: z.enum(["normal", "high", "urgent"]),
  notes: z.string().trim().max(2000).optional(),
});

type Errors = Partial<Record<keyof z.infer<typeof schema> | "files", string>>;

interface StartedCase {
  id: string;
  reference: string;
  threadId: string | null;
}

export default function NewCase() {
  const queryClient = useQueryClient();

  const [customerName, setCustomerName] = useState("");
  const [customerNameAr, setCustomerNameAr] = useState("");
  const [caseType, setCaseType] = useState("kyc_refresh");
  const [priority, setPriority] = useState("normal");
  const [notes, setNotes] = useState("");
  const [files, setFiles] = useState<PickedFile[]>([]);
  const [errors, setErrors] = useState<Errors>({});
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState<string | null>(null);
  const [started, setStarted] = useState<StartedCase | null>(null);

  const reset = () => {
    setCustomerName("");
    setCustomerNameAr("");
    setCaseType("kyc_refresh");
    setPriority("normal");
    setNotes("");
    setFiles([]);
    setErrors({});
    setStarted(null);
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const parsed = schema.safeParse({
      customer_name: customerName,
      customer_name_ar: customerNameAr,
      case_type: caseType,
      priority,
      notes,
    });

    const nextErrors: Errors = {};
    if (!parsed.success) {
      for (const issue of parsed.error.issues) {
        const key = issue.path[0] as keyof Errors;
        nextErrors[key] ??= issue.message;
      }
    }
    if (files.length === 0) nextErrors.files = "Attach at least one document.";
    setErrors(nextErrors);
    if (!parsed.success || files.length === 0) return;

    setBusy(true);
    try {
      setStage("Creating case…");
      const created = await apiFetch<CaseDetail>("/cases", {
        method: "POST",
        body: JSON.stringify({
          customer_name: parsed.data.customer_name,
          customer_name_ar: parsed.data.customer_name_ar || undefined,
          case_type: parsed.data.case_type,
          priority: parsed.data.priority,
          notes: parsed.data.notes || undefined,
        }),
      });

      setStage(`Uploading ${files.length} document${files.length === 1 ? "" : "s"}…`);
      const form = new FormData();
      for (const picked of files) form.append("files", picked.file, picked.file.name);
      await apiFetch(`/cases/${created.id}/documents`, { method: "POST", body: form });

      setStage("Starting the pipeline…");
      const startResponse = await apiFetch<StartCaseResponse>(`/cases/${created.id}/start`, {
        method: "POST",
      });

      setStarted({
        id: created.id,
        reference: created.reference,
        threadId: startResponse.thread_id ?? created.thread_id ?? null,
      });
      void queryClient.invalidateQueries({ queryKey: ["cases"] });
      toast.success("Case started", { description: `${created.reference} is now processing.` });
    } catch (error) {
      const message = describeError(error).message;
      toast.error("Could not start the case", { description: message });
      setErrors({ files: message });
    } finally {
      setBusy(false);
      setStage(null);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="New case"
        description="Create a customer case, attach the document package, and watch the agent pipeline run it end to end."
        actions={
          started ? (
            <Button variant="secondary" size="sm" onClick={reset}>
              Start another case
            </Button>
          ) : null
        }
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <Card>
          <CardHeader
            title="Case details"
            description="Synthetic customers only — this environment never holds real records."
          />
          <form onSubmit={(e) => void submit(e)} noValidate className="space-y-5 p-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                label="Customer name (English)"
                htmlFor="customer_name"
                required
                error={errors.customer_name}
              >
                <Input
                  id="customer_name"
                  value={customerName}
                  disabled={busy || Boolean(started)}
                  onChange={(e) => setCustomerName(e.target.value)}
                  aria-invalid={Boolean(errors.customer_name)}
                  placeholder="Al Noor Trading LLC"
                />
              </Field>

              <Field
                label="Customer name (Arabic)"
                htmlFor="customer_name_ar"
                hint="Optional — used for the bilingual cross-check."
                error={errors.customer_name_ar}
              >
                <Input
                  id="customer_name_ar"
                  dir="rtl"
                  value={customerNameAr}
                  disabled={busy || Boolean(started)}
                  onChange={(e) => setCustomerNameAr(e.target.value)}
                  placeholder="النور للتجارة ذ.م.م"
                />
              </Field>

              <Field label="Case type" htmlFor="case_type" required>
                <Select
                  id="case_type"
                  value={caseType}
                  onValueChange={setCaseType}
                  disabled={busy || Boolean(started)}
                  options={CASE_TYPES.map((t) => ({ value: t, label: CASE_TYPE_LABEL[t] }))}
                />
              </Field>

              <Field label="Priority" htmlFor="priority" required>
                <Select
                  id="priority"
                  value={priority}
                  onValueChange={setPriority}
                  disabled={busy || Boolean(started)}
                  options={PRIORITIES.map((p) => ({ value: p, label: PRIORITY_LABEL[p] }))}
                />
              </Field>
            </div>

            <Field
              label="Notes for the reviewer"
              htmlFor="notes"
              hint="Anything a human should know before deciding."
              error={errors.notes}
            >
              <Textarea
                id="notes"
                value={notes}
                disabled={busy || Boolean(started)}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Renewal after a change of shareholders; trade licence was reissued last month."
              />
            </Field>

            <div className="space-y-1.5">
              <p className="text-small font-medium text-ink">
                Documents
                <span className="text-danger" aria-hidden>
                  {" "}
                  *
                </span>
              </p>
              <Dropzone files={files} onChange={setFiles} disabled={busy || Boolean(started)} />
              {errors.files ? (
                <p role="alert" className="text-caption text-danger">
                  {errors.files}
                </p>
              ) : null}
            </div>

            <div className="flex items-center gap-3 border-t border-border pt-4">
              <Button
                type="submit"
                variant="primary"
                loading={busy}
                disabled={Boolean(started)}
              >
                <Rocket className="h-4 w-4" aria-hidden />
                Create and start
              </Button>
              {stage ? (
                <span className="text-small text-ink-2" aria-live="polite">
                  {stage}
                </span>
              ) : null}
            </div>
          </form>
        </Card>

        {started ? (
          <PipelineProgress
            caseId={started.id}
            reference={started.reference}
            threadId={started.threadId}
          />
        ) : (
          <Card className="h-fit">
            <CardHeader
              title="What happens next"
              description={`The same ${PIPELINE_NODES.length} steps run for every case.`}
            />
            {/* Driven by PIPELINE_NODES, so this list cannot describe a pipeline we do not run. */}
            <ol className="space-y-3 p-5">
              {PIPELINE_NODES.map((node, index) => (
                <li key={node.key} className="flex gap-3">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-surface-2 text-caption font-semibold text-ink-2 tabular">
                    {index + 1}
                  </span>
                  <div>
                    <p className="text-small font-medium text-ink">{node.label}</p>
                    <p className="text-caption text-ink-2">{node.description}</p>
                  </div>
                </li>
              ))}
            </ol>
          </Card>
        )}
      </div>
    </div>
  );
}
