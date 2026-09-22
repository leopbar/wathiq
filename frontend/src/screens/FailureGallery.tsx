import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { ArrowUpRight, FlaskConical, Play, ShieldAlert } from "lucide-react";
import { apiFetch, apiUrl, getToken } from "@/lib/api";
import { useAuth } from "@/auth/useAuth";
import { can } from "@/auth/roles";
import { PageHeader } from "@/components/PageHeader";
import { ErrorState } from "@/components/ErrorState";
import { SimulatedBadge } from "@/components/SimulatedBadge";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";
import type { CaseDetail } from "@/lib/types";

/** One entry of `GET /failure-gallery`. The texts come from the API in both languages. */
interface Scenario {
  id: string;
  category: "document" | "content" | "identity" | "process" | "model";
  title_en: string;
  title_ar: string;
  problem_en: string;
  problem_ar: string;
  detection_en: string;
  detection_ar: string;
  outcome_en: string;
  outcome_ar: string;
  where_to_look_en: string;
  where_to_look_ar: string;
  runnable: boolean;
  case_type: "kyc_refresh" | "salary_certificate";
  customer_name: string;
  expected_codes: string[];
  files: { filename: string; doc_type: string }[];
  evidence: string[];
}

type Localised = "title" | "problem" | "detection" | "outcome" | "where_to_look";

const CATEGORIES = ["document", "content", "identity", "process", "model"] as const;

type RunState = { status: "running" } | { status: "started"; caseId: string; reference: string } | {
  status: "error";
  message: string;
};

/** Fetches a scenario's synthetic PDF. `apiFetch` parses JSON, so this reads the raw bytes. */
async function downloadFile(scenarioId: string, index: number, filename: string): Promise<File> {
  const token = getToken();
  const res = await fetch(apiUrl(`/failure-gallery/${scenarioId}/files/${index}`), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`${filename}: HTTP ${res.status}`);
  return new File([await res.blob()], filename, { type: "application/pdf" });
}

/**
 * Stages a failure by sending its documents through the ordinary intake — create, upload,
 * start — exactly as a person uploading them would. There is no demo-only path.
 */
async function runScenario(scenario: Scenario): Promise<CaseDetail> {
  const files = await Promise.all(
    scenario.files.map((file, index) => downloadFile(scenario.id, index, file.filename)),
  );
  const created = await apiFetch<CaseDetail>("/cases", {
    method: "POST",
    body: JSON.stringify({
      customer_name: scenario.customer_name,
      case_type: scenario.case_type,
      priority: "normal",
      notes: `Failure-mode gallery: ${scenario.id}`,
    }),
  });
  const form = new FormData();
  for (const file of files) form.append("files", file);
  await apiFetch(`/cases/${created.id}/documents`, { method: "POST", body: form });
  await apiFetch(`/cases/${created.id}/start`, { method: "POST" });
  return created;
}

export default function FailureGallery() {
  const { t, i18n } = useTranslation();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [category, setCategory] = useState<string>("all");
  const [runs, setRuns] = useState<Record<string, RunState>>({});
  const arabic = i18n.language === "ar";
  const mayRun = can(user?.role, "case.create");

  const query = useQuery({
    queryKey: ["failure-gallery"],
    queryFn: () => apiFetch<Scenario[]>("/failure-gallery"),
    staleTime: 5 * 60_000,
  });

  const text = (scenario: Scenario, key: Localised) =>
    scenario[`${key}_${arabic ? "ar" : "en"}` as keyof Scenario] as string;

  const visible = useMemo(
    () => (query.data ?? []).filter((s) => category === "all" || s.category === category),
    [query.data, category],
  );

  const run = async (scenario: Scenario) => {
    setRuns((prev) => ({ ...prev, [scenario.id]: { status: "running" } }));
    try {
      const created = await runScenario(scenario);
      setRuns((prev) => ({
        ...prev,
        [scenario.id]: { status: "started", caseId: created.id, reference: created.reference },
      }));
      void queryClient.invalidateQueries({ queryKey: ["cases"] });
    } catch (error) {
      setRuns((prev) => ({
        ...prev,
        [scenario.id]: {
          status: "error",
          message: error instanceof Error ? error.message : String(error),
        },
      }));
    }
  };

  return (
    <div>
      <PageHeader
        title={t("gallery.title")}
        description={t("gallery.description")}
        actions={<SimulatedBadge status="simulated" />}
      />

      <div
        role="group"
        aria-label={t("gallery.filterLabel")}
        className="mb-5 flex flex-wrap items-center gap-2"
      >
        {(["all", ...CATEGORIES] as const).map((key) => (
          <button
            key={key}
            type="button"
            aria-pressed={category === key}
            onClick={() => setCategory(key)}
            className={cn(
              "rounded-full border px-3 py-1 text-small transition-colors",
              category === key
                ? "border-primary/40 bg-primary-soft text-primary"
                : "border-border bg-surface text-ink-2 hover:bg-surface-2",
            )}
          >
            {t(`gallery.category.${key}`)}
          </button>
        ))}
      </div>

      {query.isError ? (
        <ErrorState error={query.error} onRetry={() => void query.refetch()} />
      ) : query.isLoading ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {Array.from({ length: 4 }, (_, index) => (
            <Skeleton key={index} className="h-72 w-full rounded-xl" />
          ))}
        </div>
      ) : (
        <ul className="grid gap-4 lg:grid-cols-2">
          {visible.map((scenario) => {
            const state = runs[scenario.id];
            return (
              <li key={scenario.id}>
                <Card
                  className="flex h-full flex-col"
                  aria-labelledby={`gallery-${scenario.id}`}
                  role="article"
                >
                  <div className="flex flex-wrap items-center gap-2 border-b border-border px-5 py-3">
                    <Badge tone="neutral">{t(`gallery.category.${scenario.category}`)}</Badge>
                    {scenario.runnable ? (
                      <Badge tone="primary">
                        <Play className="me-1 h-3 w-3" aria-hidden />
                        {t("gallery.runnable")}
                      </Badge>
                    ) : (
                      <Badge tone="info">
                        <FlaskConical className="me-1 h-3 w-3" aria-hidden />
                        {t("gallery.provenByTests")}
                      </Badge>
                    )}
                  </div>

                  <div className="flex flex-1 flex-col gap-4 p-5">
                    <h2
                      id={`gallery-${scenario.id}`}
                      className="flex items-start gap-2 text-body font-semibold text-ink"
                    >
                      <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-warning" aria-hidden />
                      {text(scenario, "title")}
                    </h2>

                    <dl className="grid gap-3 text-small">
                      {(["problem", "detection", "outcome"] as const).map((key) => (
                        <div key={key}>
                          <dt className="text-caption font-semibold uppercase tracking-wide text-ink-2">
                            {t(`gallery.${key}`)}
                          </dt>
                          <dd className="mt-0.5 text-ink">{text(scenario, key)}</dd>
                        </div>
                      ))}
                      <div>
                        <dt className="text-caption font-semibold uppercase tracking-wide text-ink-2">
                          {t("gallery.whereToLook")}
                        </dt>
                        <dd className="mt-0.5 text-ink">{text(scenario, "where_to_look")}</dd>
                      </div>
                    </dl>

                    <div className="mt-auto border-t border-border pt-4">
                      {scenario.runnable ? (
                        <div className="flex flex-wrap items-center gap-3">
                          {mayRun ? (
                            <Button
                              variant="outlinePrimary"
                              size="sm"
                              loading={state?.status === "running"}
                              onClick={() => void run(scenario)}
                            >
                              <Play className="h-3.5 w-3.5" aria-hidden />
                              {t("gallery.run")}
                            </Button>
                          ) : (
                            <span className="text-caption text-ink-2">{t("gallery.runNotAllowed")}</span>
                          )}
                          {state?.status === "started" ? (
                            <Link
                              to={`/cases/${state.caseId}`}
                              className="inline-flex items-center gap-1 text-small font-medium text-primary hover:underline"
                            >
                              {t("gallery.openCase", { reference: state.reference })}
                              <ArrowUpRight className="h-3.5 w-3.5 rtl:-scale-x-100" aria-hidden />
                            </Link>
                          ) : null}
                          {state?.status === "error" ? (
                            <span role="alert" className="text-caption text-danger">
                              {state.message}
                            </span>
                          ) : null}
                          <p className="w-full text-caption text-ink-2">
                            {t("gallery.runHint", {
                              files: scenario.files.map((f) => f.filename).join(", "),
                            })}
                          </p>
                        </div>
                      ) : (
                        <div>
                          <p className="text-caption text-ink-2">{t("gallery.evidence")}</p>
                          <ul className="mt-1.5 space-y-1" dir="ltr">
                            {scenario.evidence.map((reference) => (
                              <li
                                key={reference}
                                className="break-all rounded bg-surface-2 px-2 py-1 font-mono text-caption text-ink-2"
                              >
                                {reference}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
