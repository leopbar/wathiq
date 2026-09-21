import { useMemo, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { toast } from "sonner";
import { Rocket } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { CaseDetail, StartCaseResponse } from "@/lib/types";
import {
  CASE_TYPES,
  PIPELINE_NODES,
  PRIORITIES,
} from "@/lib/constants";
import { describeError } from "@/components/ErrorState";
import { PageHeader } from "@/components/PageHeader";
import { Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Dropzone, type PickedFile } from "./newcase/Dropzone";
import { PipelineProgress } from "./newcase/PipelineProgress";

type FormValues = {
  customer_name: string;
  customer_name_ar?: string;
  case_type: "kyc_refresh" | "salary_certificate";
  priority: "normal" | "high" | "urgent";
  notes?: string;
};

type Errors = Partial<Record<keyof FormValues | "files", string>>;

interface StartedCase {
  id: string;
  reference: string;
  threadId: string | null;
}

export default function NewCase() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const schema = useMemo(
    () =>
      z.object({
        customer_name: z.string().trim().min(2, t("newCase.errors.customerName")),
        customer_name_ar: z.string().trim().optional(),
        case_type: z.enum(["kyc_refresh", "salary_certificate"]),
        priority: z.enum(["normal", "high", "urgent"]),
        notes: z.string().trim().max(2000, t("newCase.errors.notesLength")).optional(),
      }),
    [t],
  );

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
    if (files.length === 0) nextErrors.files = t("newCase.errors.files");
    setErrors(nextErrors);
    if (!parsed.success || files.length === 0) return;

    setBusy(true);
    try {
      setStage(t("newCase.stages.creating"));
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

      setStage(t("newCase.stages.uploading", { count: files.length }));
      const form = new FormData();
      for (const picked of files) form.append("files", picked.file, picked.file.name);
      await apiFetch(`/cases/${created.id}/documents`, { method: "POST", body: form });

      setStage(t("newCase.stages.starting"));
      const startResponse = await apiFetch<StartCaseResponse>(`/cases/${created.id}/start`, {
        method: "POST",
      });

      setStarted({
        id: created.id,
        reference: created.reference,
        threadId: startResponse.thread_id ?? created.thread_id ?? null,
      });
      void queryClient.invalidateQueries({ queryKey: ["cases"] });
      toast.success(t("newCase.started"), {
        description: t("newCase.startedDescription", { reference: created.reference }),
      });
    } catch (error) {
      const message = describeError(error).message;
      toast.error(t("newCase.startError"), { description: message });
      setErrors({ files: message });
    } finally {
      setBusy(false);
      setStage(null);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("newCase.title")}
        description={t("newCase.description")}
        actions={
          started ? (
            <Button variant="secondary" size="sm" onClick={reset}>
              {t("newCase.startAnother")}
            </Button>
          ) : null
        }
      />

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]">
        <Card>
          <CardHeader
            title={t("newCase.caseDetails")}
            description={t("newCase.syntheticOnly")}
          />
          <form onSubmit={(e) => void submit(e)} noValidate className="space-y-5 p-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                label={t("newCase.customerNameEn")}
                htmlFor="customer_name"
                required
                error={errors.customer_name}
              >
                <Input
                  id="customer_name"
                  dir="ltr"
                  value={customerName}
                  disabled={busy || Boolean(started)}
                  onChange={(e) => setCustomerName(e.target.value)}
                  aria-invalid={Boolean(errors.customer_name)}
                  placeholder="Al Noor Trading LLC"
                />
              </Field>

              <Field
                label={t("newCase.customerNameAr")}
                htmlFor="customer_name_ar"
                hint={t("newCase.customerNameArHint")}
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

              <Field label={t("newCase.caseType")} htmlFor="case_type" required>
                <Select
                  id="case_type"
                  value={caseType}
                  onValueChange={setCaseType}
                  disabled={busy || Boolean(started)}
                  options={CASE_TYPES.map((caseTypeKey) => ({
                    value: caseTypeKey,
                    label: t(`catalog.caseType.${caseTypeKey}`),
                  }))}
                />
              </Field>

              <Field label={t("newCase.priority")} htmlFor="priority" required>
                <Select
                  id="priority"
                  value={priority}
                  onValueChange={setPriority}
                  disabled={busy || Boolean(started)}
                  options={PRIORITIES.map((p) => ({
                    value: p,
                    label: t(`catalog.priority.${p}`),
                  }))}
                />
              </Field>
            </div>

            <Field
              label={t("newCase.notes")}
              htmlFor="notes"
              hint={t("newCase.notesHint")}
              error={errors.notes}
            >
              <Textarea
                id="notes"
                value={notes}
                disabled={busy || Boolean(started)}
                onChange={(e) => setNotes(e.target.value)}
                placeholder={t("newCase.notesPlaceholder")}
              />
            </Field>

            <div className="space-y-1.5">
              <p className="text-small font-medium text-ink">
                {t("newCase.documents")}
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
                {t("newCase.createAndStart")}
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
              title={t("newCase.whatNext")}
              description={t("newCase.whatNextDescription", { count: PIPELINE_NODES.length })}
            />
            {/* Driven by PIPELINE_NODES, so this list cannot describe a pipeline we do not run. */}
            <ol className="space-y-3 p-5">
              {PIPELINE_NODES.map((node, index) => (
                <li key={node.key} className="flex gap-3">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-surface-2 text-caption font-semibold text-ink-2 tabular">
                    {index + 1}
                  </span>
                  <div>
                    <p className="text-small font-medium text-ink">
                      {t(`pipeline.${node.key}.label`)}
                    </p>
                    <p className="text-caption text-ink-2">
                      {t(`pipeline.${node.key}.description`)}
                    </p>
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
